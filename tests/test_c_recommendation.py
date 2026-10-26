"""Kiểm tra C01-C04 bằng dữ liệu GIẢ LẬP (không cần tải dataset).
Chạy từ thư mục gốc repo:  python tests/test_c_recommendation.py
Lưu ý: số liệu ở đây chỉ để kiểm tra code chạy đúng, KHÔNG dùng trong báo cáo.
Số liệu báo cáo phải lấy từ:  python -m src.recommendation.evaluate  (trên catalog thật)."""
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402
from src.recommendation.build_catalog import build_catalog, validate_catalog, safe_key  # noqa: E402
from src.recommendation.recommend import Recommender, COND_RANK  # noqa: E402
from src.recommendation import evaluate as ev  # noqa: E402

SCHEMA = json.loads((ROOT / "src/features/feature_schema.json").read_text(encoding="utf-8"))
MODELS = SCHEMA["options"]["model_base_by_manufacturer"]


def make_filled(n=20000, seed=0) -> pd.DataFrame:
    """Giả lập vehicles_filled.pkl (chỉ các cột C01 cần), có cả tin đăng lặp."""
    rng = np.random.default_rng(seed)
    makes = rng.choice(list(MODELS), n)
    model = [rng.choice(MODELS[m]) for m in makes]
    year = rng.integers(1995, 2023, n)
    age = np.clip(2021 - year, 0, None)
    odo = np.clip(rng.normal(12000 * age + 8000, 15000), 0, 399_000).round()
    price = np.clip(np.exp(rng.normal(10.0, 0.5, n)) * (0.93 ** age) * 2.0, 1000, 150_000).round()
    df = pd.DataFrame({
        "id": np.arange(7_000_000_000, 7_000_000_000 + n), "manufacturer": makes, "model_base": model,
        "year": year.astype(float), "price": price, "odometer": odo,
        "condition": rng.choice(list(COND_RANK) + ["unknown"], n, p=[.01, .05, .25, .3, .1, .01, .28]),
        "type_filled": rng.choice(["sedan", "suv", "pickup", "truck", "coupe", "unknown"], n),
        "fuel_filled": rng.choice(["gas", "diesel", "hybrid", "electric"], n, p=[.85, .1, .04, .01]),
        "transmission_filled": rng.choice(["automatic", "manual", "other"], n, p=[.88, .08, .04]),
        "drive_filled": rng.choice(["4wd", "fwd", "rwd", "unknown"], n),
    })
    dup = df.sample(200, random_state=1).copy()                      # tin lặp: id mới, cùng nội dung
    dup["id"] = np.arange(8_000_000_000, 8_000_000_000 + len(dup))
    return pd.concat([df, dup], ignore_index=True)


def make_images(folder: Path, filled: pd.DataFrame):
    """Tạo vài file ảnh giả: một số đúng năm, một số chỉ khác năm."""
    sub = filled.drop_duplicates(["manufacturer", "model_base"]).head(40)
    for i, (_, r) in enumerate(sub.iterrows()):
        yr = int(r["year"]) + (0 if i % 2 == 0 else 3)
        (folder / f"{safe_key(r['manufacturer'] + '_' + r['model_base'])}_{yr}.jpg").write_bytes(b"x")


# ---------------------------------------------------------------------------
def test_c01_catalog():
    filled = make_filled()
    with tempfile.TemporaryDirectory() as tmp:
        make_images(Path(tmp), filled)
        cat, rep = build_catalog(filled, Path(tmp))
    assert validate_catalog(cat) == []
    assert cat["id"].is_unique
    assert rep["dropped_duplicate_listings"] >= 190, rep
    assert set(cat["image_match"]) <= {"exact", "nearest_year", "none"}
    assert (cat["image_match"] == "exact").any() and (cat["image_match"] == "nearest_year").any()
    assert cat.loc[cat["image_match"] == "none", "image_path"].isna().all()
    assert cat.loc[cat["image_match"] != "none", "image_path"].str.startswith("assets/car_images_unique/").all()
    # không có thư mục ảnh -> vẫn chạy, image_path trống
    cat2, _ = build_catalog(filled, None)
    assert cat2["image_path"].isna().all()
    print("C01 đạt:", len(cat), "xe;", rep["image_match_counts"])
    return cat


def make_query(budget=20000, **prefs):
    base = {"manufacturer": "ford", "model_base": "f150", "year": 2015, "type": "pickup", "odometer": 60000,
            "condition": "good", "fuel": "gas", "transmission": "automatic"}
    base.update(prefs)
    return {"budget_max_usd": budget, "preferences": {k: v for k, v in base.items() if v is not None}}


def test_c02_c03(cat):
    rec = Recommender(cat)
    for method in ("knn", "cosine"):
        for budget in (3000, 8000, 20000, 60000):
            q = make_query(budget)
            res = rec.recommend(q, method=method)
            assert len(res.cars) <= 5
            assert (res.cars["price"] <= budget).all(), "vượt ngân sách"
            assert res.cars["score"].is_monotonic_decreasing
            assert res.cars["score"].between(0, 1).all()
            assert res.cars["id"].is_unique
    # loại trừ id
    first = rec.recommend(make_query(), k=5)
    again = rec.recommend(make_query(), k=5, exclude_ids=first.cars["id"])
    assert not set(first.cars["id"]) & set(again.cars["id"])
    # điều kiện strict
    res = rec.recommend(make_query(30000), strict=("type", "fuel"))
    assert (res.cars["type"] == "pickup").all() and (res.cars["fuel"] == "gas").all()
    # ngân sách quá thấp -> không xe, có cảnh báo, không lỗi
    res = rec.recommend(make_query(1000), k=5)
    assert len(res.cars) <= 5 and ((res.cars["price"] <= 1000).all())
    res = rec.recommend({"budget_max_usd": 1.0, "preferences": {}}, k=5)
    assert len(res.cars) == 0 and res.warnings
    # thiếu ngân sách
    try:
        rec.recommend({"preferences": {}})
        raise AssertionError("phải báo lỗi")
    except ValueError:
        pass
    # ô trống: chỉ có ngân sách
    res = rec.recommend({"budget_max_usd": 15000, "preferences": {}})
    assert len(res.cars) == 5
    # giá trị chưa từng thấy không làm hỏng
    res = rec.recommend(make_query(manufacturer="khong_co", model_base="khong_co"))
    assert len(res.cars) == 5
    # cap lặp: mỗi (dòng, năm) tối đa 1 xe
    g = (res.cars["manufacturer"] + res.cars["model_base"] + res.cars["year"].astype(str))
    assert g.is_unique
    print("C02/C03 đạt")
    return rec


def test_equivalent_to_sklearn(cat):
    """Điểm tự tính phải trùng sklearn NearestNeighbors(brute) trên ma trận đã nhân trọng số."""
    from sklearn.neighbors import NearestNeighbors
    rec = Recommender(cat.sample(3000, random_state=0).reset_index(drop=True))
    q = make_query(40000)
    u, w, _ = rec._encode_query(q["budget_max_usd"], q["preferences"])
    X = (rec.M.toarray()) * w
    valid = rec.valid_indices(q)
    for metric, method in (("euclidean", "knn"), ("cosine", "cosine")):
        nn = NearestNeighbors(n_neighbors=10, algorithm="brute", metric=metric).fit(X[valid])
        dist, ind = nn.kneighbors((u * w).reshape(1, -1))
        key, _ = rec._scores(q, method)
        mine = np.sort(key[valid])[:10]
        ref = dist[0] if metric == "euclidean" else -(1 - dist[0])
        assert np.allclose(mine, ref, atol=1e-8), (metric, mine, ref)
    print("Khớp sklearn NearestNeighbors (euclidean, cosine)")


def test_similar_price(rec):
    top = rec.recommend(make_query(30000))
    res = rec.similar_price(18000, exclude_ids=top.cars["id"], preferences={"type": "pickup"})
    assert 0 < len(res.cars) <= 6
    assert not set(res.cars["id"]) & set(top.cars["id"])
    assert (res.cars["price"].sub(18000).abs() <= 18000 * 0.30 + 1e-6).all()
    assert res.cars["score"].isna().all()
    assert (res.cars["manufacturer"] + res.cars["model_base"]).is_unique       # mỗi dòng xe tối đa 1
    # có preferences -> xếp theo độ giống sở thích, không chỉ theo giá
    pref = {"manufacturer": "ford", "model_base": "f150", "year": 2015, "odometer": 60000, "type": "pickup"}
    a = rec.similar_price(18000, preferences=pref).cars
    b = rec.similar_price(18000).cars
    assert a["id"].tolist() != b["id"].tolist()
    assert (a["type"] == "pickup").mean() >= (b["type"] == "pickup").mean()
    print("similar_price đạt")


def test_cards(rec):
    from backend.schemas.result_schema import CarCard
    cards = rec.recommend(make_query()).to_cards()
    assert cards and isinstance(cards[0], CarCard) and 0 <= cards[0].score <= 1
    cards2 = rec.similar_price(15000).to_cards()
    assert cards2 and cards2[0].score is None
    json.dumps([c.__dict__ for c in cards + cards2], default=str)
    print("to_cards đạt:", cards[0].subtitle)


def test_evaluate(rec):
    table, pq = ev.evaluate(rec, n=40, seed=1, verbose=False)
    assert set(table["method"]) == set(ev.METHODS)
    assert (table["hard_constraint_rate_pct"] == 100).all(), table
    assert (table["excluded_id_leaks"] == 0).all()
    knn = table[(table.method == "knn") & (table.query_set == "from_listing")].iloc[0]
    rnd = table[(table.method == "baseline_random") & (table.query_set == "from_listing")].iloc[0]
    assert knn["precision_at_5_proxy_pct"] > rnd["precision_at_5_proxy_pct"]
    assert knn["mean_score_common"] > rnd["mean_score_common"]
    with tempfile.TemporaryDirectory() as tmp:
        ev.plot_summary(table, Path(tmp) / "a.png", 5)
    print("evaluate đạt")


if __name__ == "__main__":
    c = test_c01_catalog()
    r = test_c02_c03(c)
    test_equivalent_to_sklearn(c)
    test_similar_price(r)
    test_cards(r)
    test_evaluate(r)
    print("\nTẤT CẢ ĐỀU ĐẠT")
