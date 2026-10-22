"""
03_preprocess.py - TIỀN XỬ LÝ / LÀM SẠCH DỮ LIỆU

Thứ tự các bước (xem chi tiết lý do trong src/config.py và src/cleaning.py):
  A. Chuẩn hóa kiểu dữ liệu, chữ thường, trích seller_type từ URL
  B. Suy ra hãng xe từ tên model khi manufacturer bị thiếu
  C. Chuẩn hóa tên dòng xe: model (29.667 giá trị bẩn) -> model_base
  D. Loại dòng thiếu thông tin cốt lõi + xe ngoài phạm vi (xe máy, xe tải thương mại)
  E. Loại giá trị vô lý (giá, năm, số dặm, giá trả góp của xe mới)
  F. Khử trùng lặp (theo VIN, rồi theo nội dung)
  G. Loại giá ngoại lai theo nhóm hãng + dòng + năm
  H. Điền thiếu còn lại, tạo đặc trưng mới, ghép đặc trưng văn bản
  I. Lưu dữ liệu sạch + nhật ký làm sạch + từ điển dữ liệu

Vì sao khử trùng SAU khi lọc giá trị vô lý? Nếu khử trùng trước, có thể giữ lại
đúng bản đăng bị lỗi (vd giá = 0) rồi lại loại nó đi -> mất luôn chiếc xe đó.

Chạy: Run '03_preprocess' (~1-2 phút). Nên chạy 02_extract_text_features.py trước
(nếu chưa chạy, bước ghép đặc trưng văn bản sẽ được bỏ qua).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # thư mục gốc repo
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import pandas as pd

from src import cleaning as cl
from src import config
from src.data_loader import load_raw
from src.features import add_features


def main():
    raw = load_raw()
    log = cl.CleaningLog(len(raw))

    # A. Chuẩn hóa ---------------------------------------------------------------
    df = cl.standardize_types(raw)
    known_brands = set(df["manufacturer"].dropna().unique())
    del raw

    # B + C. Hãng xe & dòng xe ---------------------------------------------------
    df = cl.infer_manufacturer(df, known_brands)
    df = cl.add_model_base(df)
    assert len(df) == log.n_start, "merge model_base làm thay đổi số dòng!"
    df = cl.infer_manufacturer_learned(df)

    # D, E. Loại dòng thiếu / vô lý ------------------------------------------------
    df = cl.drop_missing_keys(df, log)
    df = cl.drop_invalid_values(df, log)

    # F. Trùng lặp ------------------------------------------------------------------
    df = cl.drop_duplicates(df, log)

    # G. Ngoại lai theo nhóm --------------------------------------------------------
    df, outliers = cl.drop_group_outliers(df, log)
    outliers[["id", "manufacturer", "model", "year", "odometer", "price", "price_robust_z", "seller_type"]] \
        .sort_values("price_robust_z").to_csv(config.REPORT_DIR / "removed_group_outliers.csv",
                                              index=False, encoding="utf-8-sig")

    # H. Điền thiếu + đặc trưng ------------------------------------------------------
    df = cl.handle_remaining_missing(df)
    df = add_features(df)

    if config.DESC_FEATURES_CSV.exists():
        txt = pd.read_csv(config.DESC_FEATURES_CSV)
        before = len(df)
        df = df.merge(txt, on="id", how="left", validate="one_to_one")
        assert len(df) == before
        n_nomatch = df["desc_len"].isna().sum()
        assert n_nomatch == 0, f"{n_nomatch} dòng không ghép được đặc trưng văn bản"
        print(f"   đã ghép {txt.shape[1] - 1} đặc trưng văn bản")
    else:
        print("   (bỏ qua đặc trưng văn bản - chưa chạy 02_extract_text_features.py)")

    # Bỏ các cột không dùng cho mô hình
    drop_cols = ["url", "county", "size", "VIN"]
    #   county: 100% thiếu | size: ~72% thiếu, trùng ý nghĩa với 'type'
    #   VIN: chỉ dùng để khử trùng (đã giữ cờ has_vin) | url: đã trích seller_type
    df = df.drop(columns=drop_cols)

    # I. Lưu --------------------------------------------------------------------------
    log.check_consistency(len(df))
    log.to_frame().to_csv(config.CLEANING_LOG_CSV, index=False, encoding="utf-8-sig")
    df.to_pickle(config.CLEAN_PKL)
    df.to_csv(config.CLEAN_CSV, index=False, encoding="utf-8-sig")
    build_data_dictionary(df).to_csv(config.DATA_DICT_CSV, index=False, encoding="utf-8-sig")

    print(f"\n==> Dữ liệu sạch: {len(df):,} dòng x {df.shape[1]} cột "
          f"({len(df) / log.n_start * 100:.1f}% dữ liệu gốc)")
    print(f"    {config.CLEAN_PKL}\n    {config.CLEANING_LOG_CSV}")


DESCRIPTIONS = {
    "id": "Mã tin đăng (khóa chính)", "region": "Khu vực Craigslist", "price": "Giá niêm yết (USD) - BIẾN MỤC TIÊU",
    "log_price": "log(1+price) - mục tiêu đề xuất khi train", "year": "Năm sản xuất",
    "manufacturer": "Hãng xe", "manufacturer_inferred": "0 = hãng có sẵn, 1 = suy ra từ tên hãng trong model, 2 = suy ra từ bảng dòng xe -> hãng",
    "model": "Tên model gốc (viết tự do)", "model_base": "Dòng xe đã chuẩn hóa",
    "make_model": "Hãng + dòng xe", "condition": "Tình trạng xe", "condition_rank": "Tình trạng dạng thứ bậc 0-5",
    "cylinders": "Số xi-lanh (chuỗi)", "cylinders_num": "Số xi-lanh (số)", "fuel": "Nhiên liệu",
    "odometer": "Số dặm đã đi", "log_odometer": "log(1+odometer)", "title_status": "Tình trạng giấy tờ",
    "transmission": "Hộp số", "drive": "Dẫn động", "type": "Kiểu thân xe", "paint_color": "Màu sơn",
    "state": "Bang", "lat": "Vĩ độ", "long": "Kinh độ", "posting_date": "Thời điểm đăng tin",
    "posting_dow": "Thứ trong tuần đăng tin (0 = T2)", "seller_type": "dealer = đại lý, owner = chính chủ",
    "car_age": "Tuổi xe = 2021 - year", "miles_per_year": "Số dặm trung bình mỗi năm",
    "brand_tier": "Phân khúc hãng: mainstream / luxury / exotic", "has_vin": "1 = tin có VIN",
    "n_unknown_specs": "Số thông số người bán bỏ trống (0-5)", "desc_missing": "1 = không có mô tả",
    "desc_len": "Độ dài mô tả (ký tự)", "desc_words": "Số từ trong mô tả",
}


def build_data_dictionary(df):
    rows = []
    for c in df.columns:
        rows.append({"cot": c, "kieu": str(df[c].dtype),
                     "pct_thieu": round(df[c].isna().mean() * 100, 2),
                     "so_gia_tri": df[c].nunique(),
                     "mo_ta": DESCRIPTIONS.get(c, "Cờ từ khóa trong mô tả" if c.startswith("kw_") else "")})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    main()
