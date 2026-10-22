"""
06_prepare_vin_list.py - LẬP DANH SÁCH VIN CẦN GIẢI MÃ

Dữ liệu sạch không giữ cột VIN (chỉ giữ cờ has_vin), nên ta lấy lại VIN từ file gốc theo id,
chuẩn hóa và chỉ giữ VIN hợp lệ (cùng quy tắc vin_is_valid với bước làm sạch).

Kết quả: data/interim/vins_to_decode.csv  (id, VIN, year)  -> đầu vào cho 07_vin_decode.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # thư mục gốc repo
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from src import config
from src.cleaning import vin_is_valid
from src.data_loader import load_clean, load_raw

OUT = config.INTERIM_DIR / "vins_to_decode.csv"


def main():
    df = load_clean()[["id", "year", "has_vin"]]
    raw = load_raw(usecols=["id", "VIN"], verbose=False)
    m = df.merge(raw, on="id", how="left", validate="one_to_one")
    m["VIN"] = m["VIN"].astype("string").str.strip().str.upper()
    m = m[vin_is_valid(m["VIN"])].copy()
    assert len(m) == int(df["has_vin"].sum()), "Số VIN hợp lệ lệch với cờ has_vin!"
    assert m["VIN"].is_unique, "VIN bị trùng sau khử trùng?!"
    m["year"] = m["year"].astype(int)
    m[["id", "VIN", "year"]].to_csv(OUT, index=False)
    print(f"Đã lưu {len(m):,} VIN hợp lệ ({len(m) / len(df) * 100:.1f}% số tin) -> {OUT}")
    print(f"Số lô cần gọi API (50 VIN/lô): {-(-len(m) // 50):,}")


if __name__ == "__main__":
    main()
