"""
12_split_data.py - A03: CHIA DỮ LIỆU THÀNH TẬP TRAIN / VALIDATION / TEST

Tỷ lệ 70% / 15% / 15%, random_state = 42 (config.RANDOM_STATE).
  - train      : cho mô hình học (B02), fit các bước tiền xử lý (GroupModeImputer, scaler, one-hot...)
  - validation : so sánh mô hình và chỉnh tham số (B03)
  - test       : chỉ dùng MỘT LẦN ở cuối để báo cáo kết quả (B04), không dùng để chọn mô hình

Chia theo "tầng" (stratified) của log_price chia thành 10 khoảng bằng nhau về số lượng,
để phân phối giá ở 3 tập giống nhau (không tập nào bị dồn nhiều xe rẻ hay xe đắt).

Chỉ lưu CỘT id (không lưu cả bảng) để:
  - file nhỏ, đưa được lên git;
  - mọi thành viên dùng chung một cách chia, chỉ cần ghép id với vehicles_filled.pkl.

Đầu vào : data/processed/vehicles_filled.pkl
Đầu ra  : data/splits/train_ids.csv, val_ids.csv, test_ids.csv
          reports/split_summary.csv  (so sánh 3 tập để đưa vào báo cáo)

Chạy: python 12_split_data.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # thư mục gốc repo
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import pandas as pd
from sklearn.model_selection import train_test_split

from src import config

SPLIT_DIR = config.DATA_DIR / "splits"
SUMMARY_CSV = config.REPORT_DIR / "split_summary.csv"
VAL_SIZE, TEST_SIZE = 0.15, 0.15
N_PRICE_BINS = 10


def split_ids(df):
    """Trả về 3 mảng id: train, val, test."""
    # Gán mỗi xe vào 1 trong 10 khoảng giá (mỗi khoảng ~10% số xe) để chia theo tầng
    price_bin = pd.qcut(df["log_price"], q=N_PRICE_BINS, labels=False, duplicates="drop")

    # Lần 1: tách 15% làm test
    rest_ids, test_ids, rest_bin, _ = train_test_split(
        df["id"], price_bin, test_size=TEST_SIZE,
        stratify=price_bin, random_state=config.RANDOM_STATE)

    # Lần 2: từ 85% còn lại, tách ra phần val sao cho val = 15% tổng
    val_share_of_rest = VAL_SIZE / (1 - TEST_SIZE)          # 0.15 / 0.85 ≈ 0.176
    train_ids, val_ids = train_test_split(
        rest_ids, test_size=val_share_of_rest,
        stratify=rest_bin, random_state=config.RANDOM_STATE)
    return train_ids, val_ids, test_ids


def check_split(df, parts):
    """Các kiểm tra bắt buộc: không trùng, không sót, không mất dòng."""
    sets = {k: set(v) for k, v in parts.items()}
    assert df["id"].is_unique, "id trong dữ liệu bị trùng"
    assert not (sets["train"] & sets["val"]), "train và val có id trùng nhau"
    assert not (sets["train"] & sets["test"]), "train và test có id trùng nhau"
    assert not (sets["val"] & sets["test"]), "val và test có id trùng nhau"
    assert set().union(*sets.values()) == set(df["id"]), "tổng 3 tập không bằng toàn bộ dữ liệu"
    print("Kiểm tra: không trùng id giữa các tập, không sót dòng nào -> OK")


def summarize(df, parts):
    """Bảng so sánh 3 tập: nếu chia tốt thì các con số gần như bằng nhau."""
    rows = []
    for name, ids in [("toan_bo", df["id"])] + list(parts.items()):
        d = df[df["id"].isin(ids)]
        rows.append({
            "tap": name,
            "so_dong": len(d),
            "pct": round(len(d) / len(df) * 100, 2),
            "gia_trung_binh": round(d["price"].mean()),
            "gia_trung_vi": round(d["price"].median()),
            "nam_trung_vi": d["year"].median(),
            "odometer_trung_vi": round(d["odometer"].median()),
            "pct_dai_ly": round((d["seller_type"] == "dealer").mean() * 100, 2),
            "so_hang": d["manufacturer"].nunique(),
            "so_dong_xe": d["make_model"].nunique(),
        })
    return pd.DataFrame(rows)


def main():
    df = pd.read_pickle(config.PROCESSED_DIR / "vehicles_filled.pkl")
    print(f"Đọc {len(df):,} dòng x {df.shape[1]} cột")

    train_ids, val_ids, test_ids = split_ids(df)
    parts = {"train": train_ids, "val": val_ids, "test": test_ids}
    check_split(df, parts)

    SPLIT_DIR.mkdir(parents=True, exist_ok=True)
    for name, ids in parts.items():
        out = SPLIT_DIR / f"{name}_ids.csv"
        pd.DataFrame({"id": sorted(ids)}).to_csv(out, index=False)
        print(f"  {name:5s}: {len(ids):>7,} dòng ({len(ids) / len(df) * 100:.1f}%) -> {out.name}")

    # Dòng xe chỉ có ở val/test mà train không có: mô hình chưa từng thấy -> nên biết trước
    train_mm = set(df.loc[df["id"].isin(train_ids), "make_model"])
    for name in ("val", "test"):
        mm = df.loc[df["id"].isin(parts[name]), "make_model"]
        unseen = ~mm.isin(train_mm)
        print(f"  {name}: {int(unseen.sum()):,} xe ({unseen.mean() * 100:.2f}%) thuộc dòng xe train không có")

    summary = summarize(df, parts)
    summary.to_csv(SUMMARY_CSV, index=False, encoding="utf-8-sig")
    print(f"\n==> Đã lưu {SUMMARY_CSV}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
