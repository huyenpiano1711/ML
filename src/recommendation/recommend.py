"""
recommend.py - C02 (lọc theo nhu cầu) và C03 (xếp hạng bằng KNN / Cosine).

Cách dùng (Backend D03):
    from src.recommendation.recommend import Recommender
    rec = Recommender.from_pickle()                       # nạp recommendation_catalog.pkl 1 lần
    q   = car.to_recommendation_query()                   # {"budget_max_usd", "preferences"}
    top = rec.recommend(q, k=5)                           # RecommendationResult
    alt = rec.similar_price(predicted_price, exclude_ids=top.cars["id"])
    cards = top.to_cards()                                # list[CarCard] cho giao diện

Quy trình:
  C02  Lọc điều kiện BẮT BUỘC trước: price <= budget_max_usd (theo feature_schema.json),
       loại các id bị yêu cầu loại trừ, và các trường người dùng yêu cầu `strict`.
  C03  Trên tập đã lọc, xếp hạng theo độ gần với sở thích bằng KNN (khoảng cách Euclid có
       trọng số) hoặc Cosine, rồi chọn tối đa k xe, mỗi cặp (dòng xe, năm) tối đa
       `max_per_group` xe để Top 5 không bị lặp.

Mã hóa đặc trưng (cùng một không gian cho KNN và Cosine):
  số      : price (log, theo khoảng 1.000-150.000), car_age, odometer, condition (thứ bậc),
            cờ condition_unknown                       -> thang 0-1
  phân loại: manufacturer, model_base, type, fuel, transmission, drive  -> one-hot
  Mỗi thành phần nhân một trọng số (DEFAULT_WEIGHTS). Ô người dùng bỏ trống thì trọng số = 0,
  nghĩa là không tính vào điểm.

Tính toán bằng ma trận thưa (brute force trên toàn catalog, vài chục ms); kết quả tương đương
sklearn NearestNeighbors(algorithm="brute", metric="euclidean"/"cosine") trên ma trận đã nhân
trọng số - có kiểm tra trong tests/test_c_recommendation.py.
"""
from __future__ import annotations

import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src import config  # noqa: E402

CATALOG_PKL = config.PROCESSED_DIR / "recommendation_catalog.pkl"
TOP_K = 5                       # khớp backend.schemas.result_schema.TOP_K
SIMILAR_K = 6                   # khớp MAX_ALTERNATIVES

# --- Thang chuẩn hóa (cố định, không phụ thuộc dữ liệu -> ổn định khi nạp catalog khác) ---
PRICE_RANGE = (float(config.PRICE_MIN), float(config.PRICE_MAX))
AGE_SCALE = 20.0                # tuổi >= 20 coi như xa nhất
ODO_SCALE = 200_000.0           # >= 200.000 miles coi như xa nhất
COND_RANK = {"salvage": 0, "fair": 1, "good": 2, "excellent": 3, "like new": 4, "new": 5}  # = CONDITION_ORDER
COND_MAX = 5.0

NUM_COMPONENTS = ["price", "car_age", "odometer", "condition"]
CAT_COMPONENTS = ["manufacturer", "model_base", "type", "fuel", "transmission", "drive"]
# Trọng số do C03 quyết định (feature_schema.json chỉ liệt kê cột). Có thể chỉnh và đo lại bằng evaluate.py.
DEFAULT_WEIGHTS = {
    "price": 1.5, "car_age": 2.0, "odometer": 1.5, "condition": 1.0, "cond_unknown": 0.5,
    "manufacturer": 1.0, "model_base": 2.0, "type": 1.0, "fuel": 1.0, "transmission": 0.75, "drive": 0.5,
}
PRICE_TARGET_RATIO = 0.85       # giá "lý tưởng" = 85% ngân sách (không ép dùng hết ngân sách)

DISPLAY_COLUMNS = ["id", "manufacturer", "model_base", "year", "price", "odometer", "type",
                   "condition", "fuel", "transmission", "drive", "image_path", "image_match"]


def _vn_money(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


@dataclass
class RecommendationResult:
    cars: pd.DataFrame                       # cột DISPLAY_COLUMNS + score + rank
    warnings: list[str] = field(default_factory=list)
    n_candidates: int = 0                    # số xe qua bộ lọc bắt buộc
    elapsed_ms: float = 0.0
    method: str = ""
    rows: np.ndarray = field(default_factory=lambda: np.array([], dtype=int))   # chỉ số dòng trong catalog

    def to_cards(self):
        """list[CarCard] cho giao diện (score=None với xe cùng mức giá)."""
        from backend.schemas.result_schema import CarCard
        out = []
        for _, row in self.cars.iterrows():
            score = row["score"] if "score" in row.index and pd.notna(row["score"]) else None
            out.append(CarCard.from_row(row, score=score))
        return out


class Recommender:
    def __init__(self, catalog: pd.DataFrame, method: str = "knn", weights: dict | None = None,
                 max_per_group: int = 1, price_target_ratio: float = PRICE_TARGET_RATIO):
        if method not in ("knn", "cosine"):
            raise ValueError("method phải là 'knn' hoặc 'cosine'")
        self.method = method
        self.weights = {**DEFAULT_WEIGHTS, **(weights or {})}
        self.max_per_group = max_per_group
        self.price_target_ratio = price_target_ratio

        cat = catalog.reset_index(drop=True).copy()
        for c in ["manufacturer", "model_base", "type", "condition", "fuel", "transmission", "drive"]:
            cat[c] = cat[c].astype(str)
        if "make_model" not in cat:
            cat["make_model"] = cat["manufacturer"] + " " + cat["model_base"]
        cat["image_path"] = cat["image_path"].astype(object).where(cat["image_path"].notna(), None)
        self.catalog = cat
        self._ids = cat["id"].to_numpy()
        self._price = cat["price"].to_numpy(dtype=float)
        self._group = pd.factorize(cat["make_model"] + "|" + cat["year"].astype(str))[0]
        self._encode_catalog()

    # ------------------------------------------------------------------ nạp
    @classmethod
    def from_pickle(cls, path: Path | str | None = None, **kwargs) -> "Recommender":
        path = Path(path) if path else CATALOG_PKL
        if not path.exists():
            raise FileNotFoundError(f"Chưa có {path}. Chạy: python -m src.recommendation.build_catalog")
        return cls(pd.read_pickle(path), **kwargs)

    # ------------------------------------------------------------------ mã hóa catalog
    @staticmethod
    def _price_scale(p):
        lo, hi = np.log(PRICE_RANGE[0]), np.log(PRICE_RANGE[1])
        return np.clip((np.log(np.asarray(p, dtype=float)) - lo) / (hi - lo), 0, 1)

    def _encode_catalog(self):
        cat, n = self.catalog, len(self.catalog)
        rank = cat["condition"].map(COND_RANK)
        cond_unknown = rank.isna().to_numpy(dtype=float)
        num = np.column_stack([
            self._price_scale(cat["price"]),
            np.clip(cat["car_age"].to_numpy(float) / AGE_SCALE, 0, 1),
            np.clip(cat["odometer"].to_numpy(float) / ODO_SCALE, 0, 1),
            (rank.fillna(COND_MAX / 2) / COND_MAX).to_numpy(float),
            cond_unknown,
        ])
        blocks, self._col = [sparse.csr_matrix(num)], {}
        for j, name in enumerate(["price", "car_age", "odometer", "condition", "cond_unknown"]):
            self._col[name] = j
        offset, self._levels, self._slice = num.shape[1], {}, {}
        for c in CAT_COMPONENTS:
            codes, levels = pd.factorize(cat[c])
            self._levels[c] = {v: i for i, v in enumerate(levels)}
            blocks.append(sparse.csr_matrix((np.ones(n), (np.arange(n), codes)), shape=(n, len(levels))))
            self._slice[c] = (offset, offset + len(levels))
            offset += len(levels)
        self.n_cols = offset
        self.M = sparse.hstack(blocks, format="csr")
        self.M2 = self.M.multiply(self.M).tocsr()

    # ------------------------------------------------------------------ mã hóa truy vấn
    def _encode_query(self, budget: float, prefs: dict, weights: dict | None = None):
        """Trả về (u, w, d_max): vector người dùng, vector trọng số theo cột, khoảng cách tối đa."""
        W, u, w = (weights or self.weights), np.zeros(self.n_cols), np.zeros(self.n_cols)
        dmax2 = 0.0

        def put_num(name, value, weight):
            nonlocal dmax2
            u[self._col[name]], w[self._col[name]] = value, weight
            dmax2 += weight ** 2

        put_num("price", float(self._price_scale(budget * self.price_target_ratio)), W["price"])
        if prefs.get("year") is not None:
            age = max(0.0, config.SCRAPE_YEAR - float(prefs["year"]))
            put_num("car_age", min(age / AGE_SCALE, 1.0), W["car_age"])
        if prefs.get("odometer") is not None:
            put_num("odometer", min(float(prefs["odometer"]) / ODO_SCALE, 1.0), W["odometer"])
        cond = prefs.get("condition")
        if cond in COND_RANK:
            put_num("condition", COND_RANK[cond] / COND_MAX, W["condition"])
            put_num("cond_unknown", 0.0, W["cond_unknown"])
        for c in CAT_COMPONENTS:
            value = prefs.get(c)
            if value is None or str(value).strip() == "":
                continue
            a, b = self._slice[c]
            w[a:b] = W[c]
            j = self._levels[c].get(str(value).strip().lower())
            if j is not None:
                u[a + j] = 1.0
            dmax2 += 2 * W[c] ** 2
        return u, w, float(np.sqrt(dmax2))

    # ------------------------------------------------------------------ C02: lọc bắt buộc
    def valid_indices(self, query: dict, exclude_ids=(), strict=()) -> np.ndarray:
        """Chỉ số các xe qua điều kiện BẮT BUỘC: price <= ngân sách, không nằm trong exclude_ids,
        và khớp đúng các trường trong `strict` (ví dụ ("type", "fuel"))."""
        budget = self._budget(query)
        mask = self._price <= budget
        excl = set(int(x) for x in exclude_ids)
        if excl:
            mask &= ~np.isin(self._ids, list(excl))
        prefs = query.get("preferences") or {}
        for field_name in strict:
            value = prefs.get(field_name)
            if value is not None:
                mask &= (self.catalog[field_name].to_numpy() == str(value).strip().lower())
        return np.flatnonzero(mask)

    @staticmethod
    def _budget(query: dict) -> float:
        try:
            budget = float(query["budget_max_usd"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("Thiếu 'budget_max_usd' trong yêu cầu gợi ý.")
        if not budget > 0:
            raise ValueError("'budget_max_usd' phải lớn hơn 0.")
        return budget

    # ------------------------------------------------------------------ C03: điểm
    def _scores(self, query: dict, method: str, weights: dict | None = None):
        """Trả về (key_sort, score) cho TOÀN catalog. key_sort nhỏ hơn = tốt hơn."""
        prefs = query.get("preferences") or {}
        u, w, dmax = self._encode_query(self._budget(query), prefs, weights)
        w2 = w * w
        n2 = self.M2 @ w2                       # ||x||^2 có trọng số
        dot = self.M @ (w2 * u)                 # x . u có trọng số
        u2 = float(np.sum(w2 * u * u))
        if method == "knn":
            d2 = np.maximum(n2 + u2 - 2.0 * dot, 0.0)
            d = np.sqrt(d2)
            return d, np.clip(1.0 - d / max(dmax, 1e-12), 0.0, 1.0)
        cos = dot / (np.sqrt(n2) * np.sqrt(u2) + 1e-12)
        return -cos, np.clip(cos, 0.0, 1.0)

    def score_rows(self, query: dict, rows, method: str = "knn") -> np.ndarray:
        """Điểm 0-1 của các dòng catalog bất kỳ (dùng để so với baseline trong evaluate.py)."""
        return self._scores(query, method)[1][np.asarray(rows, dtype=int)]

    # ------------------------------------------------------------------ API chính
    def recommend(self, query: dict, k: int = TOP_K, method: str | None = None,
                  exclude_ids=(), strict=(), max_per_group: int | None = None) -> RecommendationResult:
        t0 = time.perf_counter()
        method = method or self.method
        cap = self.max_per_group if max_per_group is None else max_per_group
        budget = self._budget(query)
        valid = self.valid_indices(query, exclude_ids, strict)
        warnings: list[str] = []

        if len(valid) == 0:
            warnings.append(f"Không có xe nào trong dữ liệu có giá không vượt quá {_vn_money(budget)} USD"
                            + (" và khớp các điều kiện bắt buộc." if strict else ". Hãy tăng ngân sách."))
            return RecommendationResult(self._frame([], None), warnings, 0,
                                        (time.perf_counter() - t0) * 1000, method)

        key, score = self._scores(query, method)
        order = valid[np.argsort(key[valid], kind="stable")]
        picked, used = [], Counter()
        for i in order:                                   # chọn k xe, mỗi (dòng, năm) tối đa cap xe
            if used[self._group[i]] < cap:
                picked.append(i)
                used[self._group[i]] += 1
                if len(picked) == k:
                    break
        if len(picked) < k:                               # thiếu do giới hạn lặp -> bù bằng xe tốt kế tiếp
            chosen = set(picked)
            for i in order:
                if i not in chosen:
                    picked.append(i)
                    if len(picked) == k:
                        break
        if len(picked) < k:
            warnings.append(f"Chỉ tìm được {len(picked)} xe phù hợp trong ngân sách {_vn_money(budget)} USD "
                            f"(yêu cầu {k}).")
        return RecommendationResult(self._frame(picked, score[picked]), warnings, int(len(valid)),
                                    (time.perf_counter() - t0) * 1000, method, np.asarray(picked, dtype=int))

    def similar_price(self, predicted_price: float, exclude_ids=(), k: int = SIMILAR_K,
                      preferences: dict | None = None, tolerance: float = 0.10,
                      max_tolerance: float = 0.30, max_per_model: int = 1) -> RecommendationResult:
        """'Các xe khác cùng mức giá': quy tắc lọc, không dùng mô hình.
        1) giá trong [P(1-t), P(1+t)], mở rộng t = 10% -> 15% -> 20% -> 30% đến khi đủ k xe;
        2) loại các id trong exclude_ids (Top 5);
        3) sắp xếp: nếu có `preferences` thì theo độ giống sở thích (KNN, bỏ thành phần giá vì
           đã lọc theo giá), hòa thì gần giá dự đoán hơn; không có preferences thì theo chênh lệch giá;
        4) mỗi dòng xe chọn tối đa max_per_model xe để danh sách đa dạng."""
        t0 = time.perf_counter()
        P = float(predicted_price)
        if not P > 0:
            raise ValueError("predicted_price phải lớn hơn 0.")
        excl = np.isin(self._ids, [int(x) for x in exclude_ids]) if len(list(exclude_ids)) else np.zeros(len(self._ids), bool)
        steps = sorted({t for t in (tolerance, 0.15, 0.20, max_tolerance) if tolerance <= t <= max_tolerance})
        idx, used_tol = np.array([], dtype=int), tolerance
        for t in steps:
            idx = np.flatnonzero((np.abs(self._price - P) <= P * t) & ~excl)
            used_tol = t
            if len(idx) >= k:
                break
        warnings: list[str] = []
        if len(idx) == 0:
            warnings.append(f"Không có xe nào có giá trong ±{int(max_tolerance * 100)}% của {_vn_money(P)} USD.")
            return RecommendationResult(self._frame([], None), warnings, 0, (time.perf_counter() - t0) * 1000, "price_rule")
        gap = np.abs(self._price[idx] - P)
        if preferences:
            no_price = {**self.weights, "price": 0.0}
            key, _ = self._scores({"budget_max_usd": P, "preferences": preferences}, "knn", weights=no_price)
            order = idx[np.lexsort((gap, np.round(key[idx], 6)))]
        else:
            order = idx[np.argsort(gap, kind="stable")]
        models = self.catalog["make_model"].to_numpy()
        picked, used = [], Counter()
        for i in order:
            if used[models[i]] < max_per_model:
                picked.append(i)
                used[models[i]] += 1
                if len(picked) == k:
                    break
        if len(picked) < k:
            chosen = set(picked)
            picked += [i for i in order if i not in chosen][:k - len(picked)]
        if len(picked) < k:
            warnings.append(f"Chỉ tìm được {len(picked)} xe có giá gần {_vn_money(P)} USD.")
        if used_tol > tolerance:
            warnings.append(f"Đã mở rộng khoảng giá lên ±{int(used_tol * 100)}% để đủ xe.")
        res = self._frame(picked, None)
        res["price_gap_pct"] = ((res["price"] - P) / P * 100).round(1)
        return RecommendationResult(res, warnings, int(len(idx)), (time.perf_counter() - t0) * 1000,
                                    "price_rule", np.asarray(picked, dtype=int))

    # ------------------------------------------------------------------ tiện ích
    def _frame(self, rows, scores) -> pd.DataFrame:
        cols = [c for c in DISPLAY_COLUMNS if c in self.catalog.columns]
        df = self.catalog.iloc[list(rows)][cols].reset_index(drop=True)
        if scores is not None:
            df["score"] = np.round(np.asarray(scores, dtype=float), 4)
        else:
            df["score"] = np.nan
        df["rank"] = np.arange(1, len(df) + 1)
        return df


# Hàm tiện lợi cho Backend: nạp catalog một lần
_DEFAULT: Recommender | None = None


def get_recommender() -> Recommender:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = Recommender.from_pickle()
    return _DEFAULT


def recommend(query: dict, k: int = TOP_K, **kwargs) -> RecommendationResult:
    return get_recommender().recommend(query, k=k, **kwargs)
