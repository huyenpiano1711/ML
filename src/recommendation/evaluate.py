"""
evaluate.py - C04: Đánh giá chức năng gợi ý.

Chạy từ thư mục gốc repo:
    python -m src.recommendation.evaluate                 # dùng recommendation_catalog.pkl
    python -m src.recommendation.evaluate --n 300 --seed 42

Đầu ra (reports/recommendation/):
    evaluation_results.csv   bảng chỉ số theo (bộ truy vấn, phương pháp)
    evaluation_results.json  cùng số liệu + cấu hình chạy (để báo cáo khớp kết quả thật)
    evaluation_per_query.csv chi tiết từng truy vấn
    evaluation_summary.png   biểu đồ so sánh

Phương pháp so sánh:
    knn            KNN Euclid có trọng số (mặc định của Recommender)
    cosine         Cosine Similarity trên cùng không gian đặc trưng
    baseline_random  ngẫu nhiên trong tập đã lọc theo ngân sách
    baseline_budget  xe có giá sát ngân sách nhất (không xét sở thích)
Cả bốn dùng cùng bộ lọc bắt buộc (price <= ngân sách) để so sánh công bằng.

Hai bộ truy vấn:
    from_listing  truy vấn lấy từ một tin đăng thật (bỏ chính tin đó ra khỏi ứng viên);
                  ngân sách = giá x U(1.0, 1.5). Dùng để đo độ phù hợp (precision proxy).
    random_form   tổ hợp ngẫu nhiên các ô trên form, gồm cả tổ hợp hiếm/không có thật.
                  Dùng để đo độ phủ (có tìm đủ 5 xe không) và thời gian.

Chỉ số:
    hard_constraint_rate   % xe trả về có giá <= ngân sách (kiểm tra độc lập trên catalog; phải = 100%)
    coverage_k             % truy vấn trả đủ k xe
    avg_returned           số xe trung bình trả về
    precision_at_k_proxy   % xe trả về cùng dòng xe và lệch năm <= 2 so với tin gốc (chỉ bộ from_listing).
                           Đây là chỉ số thay thế (không có nhãn ưa thích thật của người dùng),
                           đo mức nhất quán với yêu cầu, không phải mức hài lòng.
    mean_score_common      điểm KNN 0-1 trung bình, tính cùng một công thức cho mọi phương pháp
    mean_distinct_models   số dòng xe khác nhau trung bình trong Top k
    latency_mean_ms / latency_p95_ms
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src import config  # noqa: E402
from src.recommendation.recommend import Recommender, TOP_K  # noqa: E402

OUT_DIR = config.REPORT_DIR / "recommendation"
METHODS = ["knn", "cosine", "baseline_random", "baseline_budget"]
PREF_FIELDS = ["manufacturer", "model_base", "year", "type", "odometer", "condition", "fuel", "transmission", "drive"]


# ---------------------------------------------------------------------------
# Bộ truy vấn
# ---------------------------------------------------------------------------
def _round_budget(x):
    return float(np.clip(round(x / 500) * 500, 1_000, 150_000))


def make_listing_queries(cat: pd.DataFrame, n: int, rng: np.random.Generator) -> list[dict]:
    sample = cat.sample(n=min(n, len(cat)), random_state=int(rng.integers(1 << 30)))
    out = []
    for _, r in sample.iterrows():
        prefs = {f: r[f] for f in PREF_FIELDS}
        for f in ("condition", "drive", "type", "fuel", "transmission"):
            if prefs[f] == "unknown":
                prefs.pop(f)                       # người dùng bỏ trống thì không có ràng buộc
        out.append({"query": {"budget_max_usd": _round_budget(r["price"] * rng.uniform(1.0, 1.5)),
                              "preferences": prefs},
                    "source_id": int(r["id"]), "src_make_model": r["make_model"], "src_year": int(r["year"])})
    return out


def make_form_queries(cat: pd.DataFrame, n: int, rng: np.random.Generator) -> list[dict]:
    makes = cat["manufacturer"].value_counts()
    known = {c: cat.loc[cat[c] != "unknown", c].value_counts() for c in ("type", "fuel", "transmission", "condition", "drive")}
    models_by = cat.groupby("manufacturer")["model_base"].unique()
    out = []
    for _ in range(n):
        make = rng.choice(makes.index, p=(makes / makes.sum()).to_numpy())
        prefs = {"manufacturer": make, "model_base": rng.choice(models_by[make]),
                 "year": int(rng.integers(1995, 2022)), "odometer": float(rng.integers(0, 250) * 1000)}
        for f, vc in known.items():
            if f == "drive" and rng.random() < 0.5:
                continue
            prefs[f] = rng.choice(vc.index, p=(vc / vc.sum()).to_numpy())
        budget = _round_budget(float(np.exp(rng.normal(np.log(15_000), 0.8))))
        out.append({"query": {"budget_max_usd": budget, "preferences": prefs},
                    "source_id": None, "src_make_model": None, "src_year": None})
    return out


# ---------------------------------------------------------------------------
# Chạy một phương pháp
# ---------------------------------------------------------------------------
def run_method(rec: Recommender, method: str, q: dict, k: int, exclude, rng) -> tuple[np.ndarray, float]:
    """Trả về (chỉ số dòng catalog được chọn, thời gian ms)."""
    t0 = time.perf_counter()
    if method in ("knn", "cosine"):
        rows = rec.recommend(q["query"], k=k, method=method, exclude_ids=exclude).rows
    else:
        valid = rec.valid_indices(q["query"], exclude)
        if method == "baseline_random":
            rows = rng.choice(valid, size=min(k, len(valid)), replace=False) if len(valid) else np.array([], int)
        else:   # baseline_budget: giá sát ngân sách nhất
            rows = valid[np.argsort(-rec._price[valid], kind="stable")][:k]
    return rows, (time.perf_counter() - t0) * 1000


def evaluate(rec: Recommender, n: int = 300, k: int = TOP_K, seed: int = 42, verbose: bool = True):
    rng = np.random.default_rng(seed)
    cat = rec.catalog
    sets = {"from_listing": make_listing_queries(cat, n, rng), "random_form": make_form_queries(cat, n, rng)}
    price_of = dict(zip(cat["id"].astype(int), cat["price"]))      # kiểm tra độc lập với Recommender
    mm, yr = cat["make_model"].to_numpy(), cat["year"].to_numpy()
    for _ in range(3):                                              # khởi động bộ nhớ đệm, không tính thời gian
        rec.recommend(sets["random_form"][0]["query"], k=k)

    per_query = []
    for set_name, queries in sets.items():
        for qi, q in enumerate(queries):
            exclude = [q["source_id"]] if q["source_id"] is not None else []
            for method in METHODS:
                rows, ms = run_method(rec, method, q, k, exclude, rng)
                ids = rec._ids[rows].astype(int)
                budget = q["query"]["budget_max_usd"]
                row = {"query_set": set_name, "query_idx": qi, "method": method, "n_returned": len(rows),
                       "n_within_budget": int(sum(price_of[i] <= budget for i in ids)),
                       "excluded_leak": int(any(i in exclude for i in ids)),
                       "latency_ms": ms,
                       "mean_score_common": float(rec.score_rows(q["query"], rows, "knn").mean()) if len(rows) else np.nan,
                       "n_distinct_models": int(len(set(mm[rows]))) if len(rows) else 0}
                if q["src_make_model"] is not None and len(rows):
                    rel = (mm[rows] == q["src_make_model"]) & (np.abs(yr[rows] - q["src_year"]) <= 2)
                    row["relevant"], row["precision_proxy"] = int(rel.sum()), float(rel.sum() / k)
                per_query.append(row)
            if verbose and (qi + 1) % 100 == 0:
                print(f"  {set_name}: {qi + 1}/{len(queries)}")
    pq = pd.DataFrame(per_query)

    rows = []
    for (s, m), g in pq.groupby(["query_set", "method"], sort=False):
        rows.append({
            "query_set": s, "method": m, "n_queries": len(g),
            "hard_constraint_rate_pct": round(100 * g["n_within_budget"].sum() / max(g["n_returned"].sum(), 1), 2),
            f"coverage_{k}_pct": round(100 * (g["n_returned"] >= k).mean(), 2),
            "avg_returned": round(g["n_returned"].mean(), 3),
            f"precision_at_{k}_proxy_pct": round(100 * g["precision_proxy"].mean(), 2) if g["precision_proxy"].notna().any() else None,
            "mean_score_common": round(g["mean_score_common"].mean(), 4),
            "mean_distinct_models": round(g["n_distinct_models"].mean(), 3),
            "latency_mean_ms": round(g["latency_ms"].mean(), 2),
            "latency_p95_ms": round(g["latency_ms"].quantile(0.95), 2),
            "excluded_id_leaks": int(g["excluded_leak"].sum()),
        })
    return pd.DataFrame(rows), pq


def plot_summary(table: pd.DataFrame, path: Path, k: int):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(14, 4))
    a = table[table.query_set == "from_listing"].set_index("method").reindex(METHODS)
    ax[0].bar(a.index, a[f"precision_at_{k}_proxy_pct"]); ax[0].set_title(f"Precision@{k} (proxy, %) - from_listing")
    ax[1].bar(a.index, a["mean_score_common"]); ax[1].set_title("Điểm KNN trung bình (0-1)"); ax[1].set_ylim(0, 1)
    b = table[table.query_set == "random_form"].set_index("method").reindex(METHODS)
    ax[2].bar(b.index, b["latency_p95_ms"]); ax[2].set_title("Thời gian p95 (ms) - random_form")
    for x in ax:
        x.tick_params(axis="x", rotation=25)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300, help="số truy vấn mỗi bộ")
    ap.add_argument("--k", type=int, default=TOP_K)
    ap.add_argument("--seed", type=int, default=config.RANDOM_STATE)
    ap.add_argument("--catalog", type=str, default=None)
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args()

    out = Path(args.out) if args.out else OUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    rec = Recommender.from_pickle(args.catalog)
    print(f"Catalog: {len(rec.catalog):,} xe | n={args.n} truy vấn/bộ | seed={args.seed}")
    table, pq = evaluate(rec, n=args.n, k=args.k, seed=args.seed)

    table.to_csv(out / "evaluation_results.csv", index=False, encoding="utf-8-sig")
    pq.to_csv(out / "evaluation_per_query.csv", index=False, encoding="utf-8-sig")
    payload = {"config": {"n_per_set": args.n, "k": args.k, "seed": args.seed, "catalog_rows": int(len(rec.catalog)),
                          "weights": rec.weights, "max_per_group": rec.max_per_group,
                          "price_target_ratio": rec.price_target_ratio},
               "results": json.loads(table.to_json(orient="records"))}
    (out / "evaluation_results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    plot_summary(table, out / "evaluation_summary.png", args.k)
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(table.to_string(index=False))
    print(f"\nĐã lưu vào {out}")


if __name__ == "__main__":
    main()
