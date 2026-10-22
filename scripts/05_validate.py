"""
05_validate.py - DOUBLE-CHECK DỮ LIỆU SẠCH

Kiểm tra tự động (mỗi dòng in ra [OK] hoặc dừng chương trình nếu sai):
  1. Đối chiếu TỪNG DÒNG của dữ liệu sạch với file gốc theo id: price, year, odometer
     phải giữ nguyên giá trị gốc (làm sạch chỉ được LOẠI dòng, không được sửa số).
  2. Không còn trùng id, không còn trùng VIN.
  3. Mọi giá trị nằm trong khoảng đã định trong config.
  4. Không còn NaN ở cột bắt buộc; biến phân loại chỉ gồm giá trị hợp lệ.
  5. Nhật ký làm sạch khớp số dòng.
  6. Thử train nhanh mô hình baseline (Ridge trên log_price) để chắc chắn dữ liệu
     dùng được cho giai đoạn 1 và có mốc so sánh cho các mô hình sau.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # thư mục gốc repo
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
import pandas as pd

from src import config
from src.cleaning import vin_is_valid
from src.data_loader import load_clean, load_raw
from src.features import build_preprocessor, get_feature_lists

failures = []


def check(cond, msg):
    print(("   [OK]   " if cond else "   [LỖI]  ") + msg)
    if not cond:
        failures.append(msg)


df = load_clean()
print(f"Dữ liệu sạch: {len(df):,} dòng x {df.shape[1]} cột\n")

# 1. ĐỐI CHIẾU VỚI FILE GỐC ------------------------------------------------------------
print("1. Đối chiếu với file gốc theo id")
raw = load_raw(usecols=["id", "price", "year", "odometer", "manufacturer", "VIN", "url"], verbose=False)
m = df[["id", "price", "year", "odometer", "manufacturer", "manufacturer_inferred"]].merge(
    raw, on="id", how="left", suffixes=("", "_raw"), validate="one_to_one")
check(m["price_raw"].notna().all(), "mọi id trong dữ liệu sạch đều tồn tại trong file gốc")
check((m["price"] == m["price_raw"]).all(), "price giữ nguyên giá trị gốc ở 100% dòng")
check((m["year"] == m["year_raw"]).all(), "year giữ nguyên giá trị gốc ở 100% dòng")
check((m["odometer"] == m["odometer_raw"]).all(), "odometer giữ nguyên giá trị gốc ở 100% dòng")
orig = m["manufacturer_inferred"] == 0
mf_raw = m.loc[orig, "manufacturer_raw"].str.strip().str.lower().replace({"rover": "land rover"})
check((m.loc[orig, "manufacturer"] == mf_raw).all(), "manufacturer gốc không bị thay đổi (dòng không suy luận)")
check(m.loc[~orig, "manufacturer_raw"].isna().all(), "chỉ suy luận hãng cho dòng vốn bị thiếu hãng")

# 2. TRÙNG LẶP -----------------------------------------------------------------------------
print("\n2. Trùng lặp")
check(df["id"].is_unique, "id không trùng")
vins = m["VIN"].astype("string").str.strip().str.upper()
vins = vins[vin_is_valid(vins)]
check(vins.is_unique, f"VIN hợp lệ không trùng ({len(vins):,} dòng có VIN hợp lệ)")
check(df["has_vin"].sum() == len(vins), "cờ has_vin khớp với số VIN hợp lệ trong file gốc")
check((df.set_index("id")["has_vin"].loc[m["id"]].values == vin_is_valid(
    m["VIN"].astype("string").str.strip().str.upper()).astype(int).values).all(),
      "has_vin = 0 với mọi VIN rác (13131313..., 0000...)")
seller_raw = m["url"].str.extract(r"/(ct[od])/")[0].map({"ctd": "dealer", "cto": "owner"})
check((df.set_index("id")["seller_type"].loc[m["id"]].values == seller_raw.values).all(),
      "seller_type khớp với URL gốc")
n_eq = ((df["price"] == df["odometer"]) & (df["price"] > 5000)).sum()
print(f"   [INFO] số dòng có price == odometer (nghi gõ nhầm): {n_eq}")
del raw, m

# 3. KHOẢNG GIÁ TRỊ -------------------------------------------------------------------------
print("\n3. Khoảng giá trị")
check(df["price"].between(config.PRICE_MIN, config.PRICE_MAX).all(),
      f"price trong [{config.PRICE_MIN:,}; {config.PRICE_MAX:,}]")
check(df["year"].between(config.YEAR_MIN, config.YEAR_MAX).all(), f"year trong [{config.YEAR_MIN}; {config.YEAR_MAX}]")
check(df["odometer"].between(0, config.ODOMETER_MAX).all(), f"odometer trong [0; {config.ODOMETER_MAX:,}]")
check((df["car_age"] >= 0).all() and (df["car_age"] == (config.SCRAPE_YEAR - df["year"]).clip(lower=0)).all(),
      "car_age = SCRAPE_YEAR - year (>= 0)")
check(np.allclose(df["log_price"], np.log1p(df["price"])), "log_price = log1p(price)")
check(not ((df["car_age"] <= config.PAYMENT_PRICE_MAX_AGE) & (df["price"] < config.PAYMENT_PRICE_THRESHOLD)).any(),
      "không còn giá trả góp (xe mới giá < 3.000)")
lat_ok = df["lat"].dropna().between(18, 72).all() and df["long"].dropna().between(-170, -65).all()
check(lat_ok, "tọa độ nằm trong lãnh thổ Mỹ (hoặc NaN)")

# 4. THIẾU & GIÁ TRỊ HỢP LỆ --------------------------------------------------------------------
print("\n4. Giá trị thiếu và tập giá trị phân loại")
required = ["price", "year", "odometer", "manufacturer", "model_base", "make_model", "state", "seller_type",
            "condition", "fuel", "title_status", "transmission", "drive", "type", "paint_color"]
na = df[required].isna().sum()
check(na.sum() == 0, "không còn NaN ở cột bắt buộc" + ("" if na.sum() == 0 else f": {na[na > 0].to_dict()}"))
expected = {
    "condition": {"good", "excellent", "like new", "fair", "new", "salvage", "unknown"},
    "fuel": {"gas", "other", "diesel", "hybrid", "electric", "unknown"},
    "title_status": {"clean", "rebuilt", "salvage", "lien", "missing", "parts only", "unknown"},
    "transmission": {"automatic", "manual", "other", "unknown"},
    "drive": {"4wd", "fwd", "rwd", "unknown"},
    "seller_type": {"dealer", "owner"},
    "brand_tier": {"mainstream", "luxury", "exotic"},
}
for c, allowed in expected.items():
    extra = set(df[c].unique()) - allowed
    check(not extra, f"{c} chỉ gồm giá trị hợp lệ" + (f" (lạ: {extra})" if extra else ""))
check(df["state"].nunique() == 51, f"state có 51 giá trị (50 bang + DC) -> thực tế {df['state'].nunique()}")

# 5. NHẬT KÝ LÀM SẠCH ------------------------------------------------------------------------------
print("\n5. Nhật ký làm sạch")
log = pd.read_csv(config.CLEANING_LOG_CSV)
check(log["so_dong_sau"].iloc[-1] == len(df), "số dòng cuối trong log = số dòng dữ liệu sạch")
check(log["so_dong_truoc"].iloc[0] - log["bi_loai"].sum() == len(df), "dòng đầu - tổng bị loại = dòng cuối")
print(log[["buoc", "bi_loai", "pct_loai_so_voi_goc"]].to_string(index=False))

# 6. BASELINE ---------------------------------------------------------------------------------------
print("\n6. Mô hình baseline (kiểm tra dữ liệu sẵn sàng cho Giai đoạn 1)")
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

num, cat, high = get_feature_lists(df)
X, y = df[num + cat + high], df["log_price"]
X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=config.RANDOM_STATE)
print(f"   train {len(X_tr):,} / test {len(X_te):,} | {len(num)} biến số, {len(cat) + len(high)} biến phân loại")
for name, model in [("Dummy (luôn đoán trung vị)", DummyRegressor(strategy="median")),
                    ("Ridge + one-hot", Ridge(alpha=1.0))]:
    t0 = time.time()
    pipe = Pipeline([("prep", build_preprocessor(num, cat, high)), ("model", model)])
    pipe.fit(X_tr, y_tr)
    pred = pipe.predict(X_te)
    mae = mean_absolute_error(np.expm1(y_te), np.expm1(pred))
    print(f"   {name:28s} R2(log) = {r2_score(y_te, pred):.3f} | MAE = ${mae:,.0f} | {time.time() - t0:.0f}s")

print("\n" + ("==> TẤT CẢ KIỂM TRA ĐỀU ĐẠT" if not failures else f"==> CÓ {len(failures)} LỖI: {failures}"))
sys.exit(1 if failures else 0)
