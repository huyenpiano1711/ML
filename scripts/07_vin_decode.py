"""
07_vin_decode.py - GIẢI MÃ VIN QUA API MIỄN PHÍ CỦA NHTSA (cần internet)

API: https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVINValuesBatch/  (tối đa 50 VIN/lần)
Gửi kèm năm sản xuất của tin đăng ("VIN,năm") để API giải mã chính xác hơn.

  - Mỗi lô 50 VIN lưu thành 1 file JSON trong data/interim/vin_cache/ -> dừng giữa chừng
    (đóng cửa sổ / Ctrl+C / mất mạng) rồi chạy lại sẽ tiếp tục, không gọi lại lô đã xong.
  - Xong tất cả -> gộp thành data/interim/vin_decoded.csv (1 dòng / 1 VIN).

Chạy: python 07_vin_decode.py (Windows: có thể nhấp đúp giai_ma_vin.bat), khoảng 1-2 giờ.
Cần chạy 06_prepare_vin_list.py trước (đã có sẵn vins_to_decode.csv thì bỏ qua).
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # thư mục gốc repo
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import pandas as pd
import requests

from src import config

API = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVINValuesBatch/"
UA = "AutoWiseAcademicProject/1.0 (UEL student project; khadlqk24416@st.uel.edu.vn)"
BATCH = 50
DELAY = 0.5                 # giây nghỉ giữa 2 lô (lịch sự với máy chủ)
MAX_RETRY = 5
IN_CSV = config.INTERIM_DIR / "vins_to_decode.csv"
CACHE = config.INTERIM_DIR / "vin_cache"
OUT_CSV = config.INTERIM_DIR / "vin_decoded.csv"

# Các trường giữ lại từ ~140 trường NHTSA trả về
KEEP = ["VIN", "ErrorCode", "ErrorText", "Make", "Model", "ModelYear", "Trim", "Series",
        "BodyClass", "VehicleType", "DriveType", "EngineCylinders", "DisplacementL",
        "EngineHP", "FuelTypePrimary", "FuelTypeSecondary", "ElectrificationLevel",
        "TransmissionStyle", "TransmissionSpeeds", "Doors", "GVWR", "PlantCountry"]

session = requests.Session()
session.headers.update({"User-Agent": UA})


def decode_batch(pairs):
    data = {"format": "json", "data": ";".join(f"{v},{y}" for v, y in pairs)}
    for attempt in range(1, MAX_RETRY + 1):
        try:
            r = session.post(API, data=data, timeout=90)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {r.status_code}")
            r.raise_for_status()
            res = r.json()["Results"]
            if sorted((x.get("VIN") or "").upper() for x in res) != sorted(v for v, _ in pairs):
                raise ValueError(f"API trả {len(res)} kết quả không khớp {len(pairs)} VIN đã gửi")
            return [{k: (x.get(k) or "").strip() for k in KEEP} for x in res]
        except Exception as e:
            if attempt == MAX_RETRY:
                raise
            wait = 5 * attempt
            print(f"   lỗi ({type(e).__name__}: {str(e)[:60]}) -> thử lại sau {wait}s", flush=True)
            time.sleep(wait)


def main():
    if not IN_CSV.exists():
        sys.exit(f"Không thấy {IN_CSV} -> chạy 06_prepare_vin_list.py trước.")
    CACHE.mkdir(parents=True, exist_ok=True)
    vins = pd.read_csv(IN_CSV)
    pairs = list(zip(vins["VIN"], vins["year"]))
    batches = [pairs[i:i + BATCH] for i in range(0, len(pairs), BATCH)]
    done = sum((CACHE / f"batch_{i:05d}.json").exists() for i in range(len(batches)))
    print(f"{len(pairs):,} VIN | {len(batches):,} lô | đã xong trước đó: {done:,}")

    t0, n_new = time.time(), 0
    try:
        for i, b in enumerate(batches):
            f = CACHE / f"batch_{i:05d}.json"
            if f.exists():
                continue
            rows = decode_batch(b)
            tmp = f.with_suffix(".part")
            tmp.write_text(json.dumps(rows), encoding="utf-8")
            tmp.replace(f)
            n_new += 1
            if n_new == 1 or n_new % 20 == 0:
                rate = (time.time() - t0) / n_new
                left = (len(batches) - done - n_new) * rate / 60
                print(f"   lô {i + 1:,}/{len(batches):,} | {rate:.1f}s/lô | còn khoảng {left:.0f} phút", flush=True)
            time.sleep(DELAY)
    except KeyboardInterrupt:
        print("\nĐã dừng. Chạy lại để tiếp tục từ lô dở.")
        return

    files = sorted(CACHE.glob("batch_*.json"))
    rows = [r for f in files for r in json.loads(f.read_text(encoding="utf-8"))]
    out = pd.DataFrame(rows)
    out["VIN"] = out["VIN"].str.upper()
    # Kiểm tra chéo: đủ số VIN, mỗi VIN đúng 1 kết quả, khớp đúng tập VIN đã gửi
    assert len(out) == len(pairs), f"Thiếu kết quả: {len(out)} / {len(pairs)}"
    assert out["VIN"].is_unique and set(out["VIN"]) == set(vins["VIN"]), "VIN trả về không khớp VIN gửi đi!"
    out = vins[["id", "VIN"]].merge(out, on="VIN", how="left", validate="one_to_one")
    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n==> Đã lưu {len(out):,} VIN vào {OUT_CSV}")
    codes = out["ErrorCode"].fillna("").str.split(",").str[0].value_counts(normalize=True).mul(100).round(1)
    print("    Mã kết quả NHTSA (0 = giải mã đầy đủ):", codes.head(6).to_dict())
    print("    Bước tiếp: báo lại để chạy 08_fill_specs.py")


if __name__ == "__main__":
    main()
