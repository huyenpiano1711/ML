"""
build_catalog.py - C01: Tạo danh sách xe để gợi ý (recommendation_catalog.pkl).

Đầu vào : data/processed/vehicles_filled.pkl   (198.514 x 65, bản data-v1)
Đầu ra  : data/processed/recommendation_catalog.pkl
          reports/recommendation/catalog_report.json   (số liệu kiểm tra, dùng cho báo cáo)

Chạy từ thư mục gốc repo:
    python -m src.recommendation.build_catalog

Quy ước:
  - Cột thông số xe lấy bản đã điền (type_filled, fuel_filled, transmission_filled,
    drive_filled); điều kiện (condition) giữ nguyên vì nhóm chủ đích không điền.
  - Tên cột trùng `recommendation_columns.display` trong feature_schema.json và trùng
    các trường của CarCard (backend/schemas/result_schema.py).
  - Ảnh là ảnh minh họa theo (hãng, dòng, năm), không phải ảnh thật của tin đăng.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # cho phép chạy trực tiếp file
from src import config  # noqa: E402

FILLED_PKL = config.PROCESSED_DIR / "vehicles_filled.pkl"
CATALOG_PKL = config.PROCESSED_DIR / "recommendation_catalog.pkl"
REPORT_DIR = config.REPORT_DIR / "recommendation"
IMAGE_REL_DIR = "assets/car_images_unique"          # đường dẫn tương đối so với gốc repo

# Cột đầu ra của catalog
CATALOG_COLUMNS = ["id", "manufacturer", "model_base", "make_model", "year", "car_age",
                   "price", "odometer", "type", "condition", "fuel", "transmission", "drive",
                   "image_path", "image_match"]
# Cột bắt buộc có giá trị (không thiếu)
REQUIRED_NOT_NULL = ["id", "manufacturer", "model_base", "year", "price", "odometer",
                     "type", "condition", "fuel", "transmission", "drive"]
# Cột dùng để phát hiện tin đăng lặp (cùng xe đăng ở nhiều khu vực)
DUP_KEYS = ["manufacturer", "model_base", "year", "price", "odometer",
            "type", "condition", "fuel", "transmission", "drive"]


def safe_key(value: str) -> str:
    """Cùng quy tắc với safe_filename() trong scripts/download_car_images.py."""
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower().strip()).strip("_")[:120]


# ---------------------------------------------------------------------------
# Ghép ảnh
# ---------------------------------------------------------------------------
def scan_images(image_dir: Path) -> pd.DataFrame:
    """Đọc tên file ảnh dạng '<hang>_<dong>_<nam>.jpg' -> bảng (model_key, year, file)."""
    rows = []
    if image_dir is not None and Path(image_dir).is_dir():
        for p in Path(image_dir).iterdir():
            m = re.match(r"^(.*)_(\d{4})\.(jpg|jpeg|png)$", p.name.lower())
            if m:
                rows.append((m.group(1), int(m.group(2)), p.name))
    return pd.DataFrame(rows, columns=["model_key", "year", "file"])


def attach_images(cat: pd.DataFrame, image_dir: Path | None) -> pd.DataFrame:
    """Thêm image_path + image_match.
    image_match: 'exact' (đúng hãng-dòng-năm), 'nearest_year' (cùng dòng, năm gần nhất),
    'none' (không có ảnh nào của dòng này -> Frontend dùng ảnh thay thế)."""
    cat = cat.copy()
    cat["image_path"] = None
    cat["image_match"] = "none"
    imgs = scan_images(image_dir)
    if imgs.empty:
        return cat
    by_model = {k: g.sort_values("year") for k, g in imgs.groupby("model_key")}
    combos = cat[["manufacturer", "model_base", "year"]].drop_duplicates().copy()
    combos["model_key"] = (combos["manufacturer"].astype(str) + "_" + combos["model_base"].astype(str)).map(safe_key)
    found = {}
    for key, year in zip(combos["model_key"], combos["year"]):
        g = by_model.get(key)
        if g is None:
            continue
        gap = (g["year"] - year).abs()
        j = gap.to_numpy().argmin()                      # năm gần nhất (hòa -> năm nhỏ hơn)
        found[(key, year)] = (f"{IMAGE_REL_DIR}/{g['file'].iloc[j]}",
                              "exact" if gap.iloc[j] == 0 else "nearest_year")
    keys = (cat["manufacturer"].astype(str) + "_" + cat["model_base"].astype(str)).map(safe_key)
    pairs = list(zip(keys, cat["year"]))
    hit = [found.get(p) for p in pairs]
    cat["image_path"] = pd.Series([h[0] if h else None for h in hit], index=cat.index, dtype="object")
    cat["image_match"] = pd.Series([h[1] if h else "none" for h in hit], index=cat.index)
    return cat


# ---------------------------------------------------------------------------
# Kiểm tra chất lượng
# ---------------------------------------------------------------------------
def validate_catalog(cat: pd.DataFrame) -> list[str]:
    """Trả về danh sách lỗi (rỗng = đạt)."""
    problems = []
    missing_cols = [c for c in CATALOG_COLUMNS if c not in cat.columns]
    if missing_cols:
        return [f"Thiếu cột: {missing_cols}"]
    if cat["id"].duplicated().any():
        problems.append(f"Có {int(cat['id'].duplicated().sum())} id bị trùng.")
    for c in REQUIRED_NOT_NULL:
        n = int(cat[c].isna().sum())
        if n:
            problems.append(f"Cột {c} thiếu {n} giá trị.")
    if not cat["price"].between(config.PRICE_MIN, config.PRICE_MAX).all():
        problems.append("Có giá ngoài khoảng cho phép.")
    if not cat["odometer"].between(0, config.ODOMETER_MAX).all():
        problems.append("Có odometer ngoài khoảng cho phép.")
    if not cat["year"].between(config.YEAR_MIN, config.YEAR_MAX).all():
        problems.append("Có năm sản xuất ngoài khoảng cho phép.")
    return problems


# ---------------------------------------------------------------------------
# Quy trình chính
# ---------------------------------------------------------------------------
def build_catalog(df: pd.DataFrame, image_dir: Path | None = None) -> tuple[pd.DataFrame, dict]:
    """df: vehicles_filled (đọc từ pkl). Trả về (catalog, report)."""
    report = {"rows_input": int(len(df))}

    cat = pd.DataFrame({
        "id": df["id"].astype("int64"),
        "manufacturer": df["manufacturer"], "model_base": df["model_base"],
        "year": df["year"], "price": df["price"], "odometer": df["odometer"],
        "type": df["type_filled"], "condition": df["condition"],
        "fuel": df["fuel_filled"], "transmission": df["transmission_filled"],
        "drive": df["drive_filled"],
    })

    # 1. Bỏ dòng thiếu thông tin quan trọng
    before = len(cat)
    cat = cat.dropna(subset=["id", "manufacturer", "model_base", "year", "price", "odometer"])
    report["dropped_missing_core"] = int(before - len(cat))
    for c in ["manufacturer", "model_base", "type", "condition", "fuel", "transmission", "drive"]:
        cat[c] = cat[c].astype(str).str.strip().str.lower()
        cat.loc[cat[c].isin(["", "nan", "none", "<na>"]), c] = "unknown"
    cat["year"] = cat["year"].astype(int)
    cat["price"] = cat["price"].astype(float)
    cat["odometer"] = cat["odometer"].astype(float)

    # 2. Bỏ tin đăng lặp (cùng xe, nhiều khu vực): giữ dòng có id nhỏ nhất
    before = len(cat)
    cat = cat.sort_values("id").drop_duplicates(subset=DUP_KEYS, keep="first")
    report["dropped_duplicate_listings"] = int(before - len(cat))

    # 3. Cột phụ
    cat["make_model"] = cat["manufacturer"] + " " + cat["model_base"]
    cat["car_age"] = (config.SCRAPE_YEAR - cat["year"]).clip(lower=0).astype(int)

    # 4. Ảnh minh họa
    cat = attach_images(cat, image_dir)
    report["image_dir_found"] = bool(image_dir is not None and Path(image_dir).is_dir())
    report["image_match_counts"] = {k: int(v) for k, v in cat["image_match"].value_counts().items()}

    cat = cat[CATALOG_COLUMNS].reset_index(drop=True)

    # 5. Kiểm tra cuối
    problems = validate_catalog(cat)
    report["rows_output"] = int(len(cat))
    report["unique_ids"] = int(cat["id"].nunique())
    report["n_manufacturers"] = int(cat["manufacturer"].nunique())
    report["n_make_models"] = int(cat["make_model"].nunique())
    report["share_unknown_pct"] = {c: round(float((cat[c] == "unknown").mean() * 100), 2)
                                   for c in ["type", "condition", "fuel", "transmission", "drive"]}
    report["problems"] = problems
    if problems:
        raise ValueError("Catalog không đạt kiểm tra: " + "; ".join(problems))
    return cat, report


def main():
    if not FILLED_PKL.exists():
        sys.exit(f"Không thấy {FILLED_PKL}. Tải autowise_data_processed.zip ở Release data-v1 (xem README).")
    df = pd.read_pickle(FILLED_PKL)
    image_dir = config.IMAGE_DIR if config.IMAGE_DIR.is_dir() else None
    if image_dir is None:
        print("CẢNH BÁO: chưa có assets/car_images_unique -> image_path để trống.")
    cat, report = build_catalog(df, image_dir)
    cat.to_pickle(CATALOG_PKL)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "catalog_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nĐã lưu {len(cat):,} xe -> {CATALOG_PKL}")


if __name__ == "__main__":
    main()
