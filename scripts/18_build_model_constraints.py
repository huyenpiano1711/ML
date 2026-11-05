"""
18_build_model_constraints.py - Tạo src/features/model_constraints.json: với mỗi dòng xe (hãng + dòng),
khoảng năm sản xuất, kiểu dáng, nhiên liệu và hộp số có thật trong dữ liệu.

    python scripts/18_build_model_constraints.py

Đầu vào: data/processed/recommendation_catalog.pkl (cùng dữ liệu với mô hình gợi ý).
Quy tắc (giải thích trong src/features/model_constraints.py):
  - year: min..max của các năm có >= MIN_YEAR_COUNT tin, nới 1 năm mỗi đầu nếu năm đó có tin.
  - type/fuel/transmission: giữ giá trị có >= MIN_COUNT tin hoặc >= MIN_SHARE số tin; bỏ 'unknown'.
    Luôn giữ ít nhất giá trị phổ biến nhất (khi dòng xe có giá trị khác 'unknown').
"""
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

import pandas as pd  # noqa: E402

from backend.schemas.vehicle_input import FEATURES  # noqa: E402
from src.features.model_constraints import CATEGORICAL, CONSTRAINTS_PATH  # noqa: E402

CATALOG = PROJECT_DIR / "data" / "processed" / "recommendation_catalog.pkl"
MIN_YEAR_COUNT = 2
MIN_COUNT = 5
MIN_SHARE = 0.10


def year_range(years: pd.Series) -> list[int]:
    counts = years.value_counts()
    solid = counts[counts >= MIN_YEAR_COUNT].index
    lo, hi = (solid.min(), solid.max()) if len(solid) else (years.min(), years.max())
    if lo - 1 in counts.index:
        lo -= 1
    if hi + 1 in counts.index:
        hi += 1
    year_min, year_max = int(FEATURES["year"]["min"]), int(FEATURES["year"]["max"])
    return [max(int(lo), year_min), min(int(hi), year_max)]


def allowed_values(values: pd.Series, options: list[str]) -> list[str]:
    counts = values[values.isin(options)].value_counts()
    if counts.empty:
        return []
    keep = counts[(counts >= MIN_COUNT) | (counts / len(values) >= MIN_SHARE)]
    keep = keep if len(keep) else counts.head(1)
    return sorted(keep.index, key=options.index)              # cùng thứ tự với ô chọn trên form


def main():
    cat = pd.read_pickle(CATALOG)
    models = {}
    for (make, model), group in cat.groupby(["manufacturer", "model_base"]):
        entry = {"n": int(len(group)), "year": year_range(group["year"].astype(int))}
        for name in CATEGORICAL:
            entry[name] = allowed_values(group[name].astype(str), FEATURES[name]["ui_options"])
        models.setdefault(str(make), {})[str(model)] = entry
    out = {"source": "data/processed/recommendation_catalog.pkl",
           "rules": {"min_year_count": MIN_YEAR_COUNT, "min_count": MIN_COUNT, "min_share": MIN_SHARE},
           "models": models}
    CONSTRAINTS_PATH.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    n_models = sum(len(v) for v in models.values())
    print(f"Đã ghi {CONSTRAINTS_PATH} ({n_models} dòng xe, {CONSTRAINTS_PATH.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
