"""
01_eda_raw.py - KHÁM PHÁ DỮ LIỆU GỐC (trước khi làm sạch)

Mục tiêu: hiểu "sức khỏe" của bộ dữ liệu để quyết định các bước tiền xử lý.
Kết quả:
  reports/eda_raw/*.png              biểu đồ
  reports/eda_raw/overview.csv       bảng tổng quan từng cột (kiểu, % thiếu, số giá trị...)
  reports/eda_raw/numeric_describe.csv
  reports/eda_raw/summary_raw.md     tóm tắt các con số quan trọng (dùng cho báo cáo)

Chạy: chuột phải vào file -> Run '01_eda_raw' (mất ~1-2 phút vì file lớn).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # thư mục gốc repo
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
import pandas as pd

from src import config
from src import plot_utils as pu
from src.data_loader import load_raw

OUT = config.EDA_RAW_DIR
lines = []  # nội dung file summary_raw.md


def note(text=""):
    print(text)
    lines.append(text)


def pct(a, b):
    return f"{a / b * 100:.2f}%"


# ---------------------------------------------------------------------------
df = load_raw()
N = len(df)
note("# EDA dữ liệu gốc - Craigslist Cars & Trucks\n")
note(f"- Số dòng: **{N:,}**, số cột đọc vào: **{df.shape[1]}** "
     "(chưa tính description, image_url, region_url)")

# 1. TỔNG QUAN TỪNG CỘT ------------------------------------------------------
note("\n## 1. Tổng quan cột")
overview = pd.DataFrame({
    "dtype": df.dtypes.astype(str),
    "n_missing": df.isna().sum(),
    "pct_missing": (df.isna().mean() * 100).round(2),
    "n_unique": df.nunique(),
    "vi_du": [", ".join(map(str, df[c].dropna().unique()[:4])) for c in df.columns],
}).sort_values("pct_missing", ascending=False)
overview.to_csv(OUT / "overview.csv", encoding="utf-8-sig")
note(overview[["dtype", "pct_missing", "n_unique"]].to_string())

miss = overview["pct_missing"][overview["pct_missing"] > 0]
pu.barh(miss, "Tỷ lệ thiếu dữ liệu theo cột (%)", OUT / "01_missing_pct.png",
        xlabel="% dòng bị thiếu", fmt=pu.mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))

# Dòng "gần như rỗng": chỉ có price + state, thiếu cả năm và hãng
empty_rows = df[["year", "manufacturer", "model", "odometer"]].isna().all(axis=1).sum()
note(f"\n- Dòng thiếu đồng thời year + manufacturer + model + odometer: {empty_rows:,}")
note(f"- Cột county thiếu {overview.loc['county', 'pct_missing']}% -> loại bỏ hoàn toàn")

# 2. BIẾN MỤC TIÊU: PRICE -----------------------------------------------------
note("\n## 2. Biến mục tiêu price")
p = df["price"]
desc = p.describe(percentiles=[.01, .05, .1, .25, .5, .75, .9, .95, .99, .999])
note(desc.apply(lambda x: f"{x:,.0f}").to_string())
for t in [0, 500, 1000]:
    note(f"- price <= {t:,}: {(p <= t).sum():,} dòng ({pct((p <= t).sum(), N)})")
for t in [150_000, 1_000_000]:
    note(f"- price > {t:,}: {(p > t).sum():,} dòng")
note("- 15 mức giá xuất hiện nhiều nhất (dấu hiệu định giá kiểu đại lý ...995, ...990):")
note(p.value_counts().head(15).to_string())

pu.hist(p[(p > 0) & (p <= 150_000)], "Phân phối giá (0 < price <= 150k) - lệch phải mạnh",
        OUT / "02_price_hist.png", xlabel="Giá niêm yết (USD)", fmt=pu.usd,
        vlines={"PRICE_MIN": config.PRICE_MIN})
pu.hist(p[p > 0], "Phân phối giá trên thang log (toàn bộ price > 0)",
        OUT / "03_price_hist_log.png", xlabel="Giá (USD, thang log)", log_x=True, fmt=pu.usd,
        vlines={"MIN": config.PRICE_MIN, "MAX": config.PRICE_MAX})

# 3. NGƯỜI BÁN: ĐẠI LÝ hay CHÍNH CHỦ (trích từ URL) -------------------------
note("\n## 3. Loại người bán (trích từ URL: /ctd/ = dealer, /cto/ = owner)")
df["seller_type"] = df["url"].str.extract(r"/(ct[od])/")[0].map({"ctd": "dealer", "cto": "owner"})
note(df["seller_type"].value_counts(dropna=False).to_string())
zero = df[p == 0]["seller_type"].value_counts()
note(f"- Trong {(p == 0).sum():,} tin price = 0: dealer {zero.get('dealer', 0):,}, "
     f"owner {zero.get('owner', 0):,} -> price=0 chủ yếu là 'liên hệ để biết giá' của đại lý")

# 4. YEAR & ODOMETER -----------------------------------------------------------
note("\n## 4. Năm sản xuất và số dặm")
y = df["year"]
note(f"- year: min {y.min():.0f}, max {y.max():.0f}, thiếu {y.isna().sum():,}")
note(f"- year < {config.YEAR_MIN}: {(y < config.YEAR_MIN).sum():,} dòng ({pct((y < config.YEAR_MIN).sum(), N)})")
pu.hist(y, "Phân phối năm sản xuất", OUT / "04_year_hist.png", bins=np.arange(1900, 2024),
        xlabel="Năm", vlines={"YEAR_MIN": config.YEAR_MIN})

o = df["odometer"]
note(o.describe(percentiles=[.01, .5, .99, .999]).apply(lambda x: f"{x:,.0f}").to_string())
note(f"- odometer = 0: {(o == 0).sum():,}; odometer > {config.ODOMETER_MAX:,}: "
     f"{(o > config.ODOMETER_MAX).sum():,}")
note("- Giá trị odometer lặp nhiều nhất (giá trị 'tròn' / giữ chỗ):")
note(o.value_counts().head(8).to_string())
pu.hist(o[o <= 500_000], "Phân phối số dặm đã đi (odometer <= 500k)",
        OUT / "05_odometer_hist.png", xlabel="Dặm", fmt=pu.thousands,
        vlines={"ODOMETER_MAX": config.ODOMETER_MAX})

# 5. BIẾN PHÂN LOẠI -------------------------------------------------------------
note("\n## 5. Biến phân loại")
for c in config.CATEGORICAL_LOW_CARD:
    vc = df[c].fillna("(thiếu)").value_counts()
    note(f"\n**{c}**: " + ", ".join(f"{k} {v:,}" for k, v in vc.items()))
    pu.barh(vc, f"{c} - số tin đăng (kể cả thiếu)", OUT / f"06_cat_{c}.png")

mf = df["manufacturer"].fillna("(thiếu)").value_counts()
note(f"\n- manufacturer: {df['manufacturer'].nunique()} hãng; 5 hãng lớn nhất chiếm "
     f"{pct(mf.drop('(thiếu)', errors='ignore').head(5).sum(), N)}")
pu.barh(mf.head(25), "Top 25 hãng xe theo số tin đăng", OUT / "07_manufacturer_top25.png")
note(f"- model: {df['model'].nunique():,} giá trị khác nhau (viết tự do, rất bẩn). Ví dụ: "
     + "; ".join(df["model"].dropna().sample(8, random_state=1)))
pu.barh(df["state"].value_counts().head(20), "Top 20 bang theo số tin đăng",
        OUT / "08_state_top20.png")

# 6. TRÙNG LẶP -----------------------------------------------------------------
note("\n## 6. Trùng lặp")
note(f"- Trùng id: {df['id'].duplicated().sum():,}")
v = df.dropna(subset=["VIN"])
vin_counts = v["VIN"].value_counts()
note(f"- Có VIN: {len(v):,} dòng, {v['VIN'].nunique():,} VIN khác nhau -> "
     f"{v['VIN'].duplicated().sum():,} dòng đăng lặp cùng một chiếc xe")
note(f"- VIN bị đăng nhiều nhất: {vin_counts.iloc[0]} lần ({vin_counts.index[0]}), "
     f"trải trên {v[v['VIN'] == vin_counts.index[0]]['region'].nunique()} khu vực -> đại lý đăng tràn lan")
g = v.groupby("VIN")["price"].nunique()
note(f"- Trong các VIN lặp, {pct((g[vin_counts[vin_counts > 1].index] > 1).sum(), (vin_counts > 1).sum())}"
     " có nhiều mức giá khác nhau (đổi giá khi đăng lại) -> giữ tin mới nhất")
content_key = ["price", "year", "manufacturer", "model", "odometer", "condition", "fuel",
               "transmission", "type", "paint_color", "state"]
note(f"- Trùng toàn bộ nội dung chính (không xét VIN): {df.duplicated(subset=content_key).sum():,}")
bins = pd.cut(vin_counts, [0, 1, 2, 3, 5, 10, 20, 50, 1000],
              labels=["1 lần", "2 lần", "3 lần", "4-5 lần", "6-10 lần", "11-20 lần", "21-50 lần", "> 50 lần"])
vc_dup = bins.value_counts().sort_index()
pu.barh(vc_dup, "Một VIN được đăng bao nhiêu lần? (số VIN theo nhóm)", OUT / "09_vin_repost.png",
        xlabel="Số VIN", sort=False)
rows_by_bin = vin_counts.groupby(bins, observed=True).sum()
note("- Số TIN ĐĂNG theo nhóm lặp: " + ", ".join(f"{k}: {v:,}" for k, v in rows_by_bin.items()))

# 7. THỜI GIAN & TỌA ĐỘ ---------------------------------------------------------
note("\n## 7. Thời gian đăng tin và tọa độ")
pdt = pd.to_datetime(df["posting_date"], utc=True, errors="coerce")
note(f"- posting_date: từ {pdt.min()} đến {pdt.max()} -> chọn SCRAPE_YEAR = 2021")
out_us = ((df["lat"] < 18) | (df["lat"] > 72) | (df["long"] > -65) | (df["long"] < -170)).sum()
note(f"- Tọa độ nằm ngoài lãnh thổ Mỹ: {out_us:,} dòng -> đặt NaN")

# 8. QUAN HỆ SƠ BỘ GIỮA GIÁ VÀ CÁC BIẾN (chỉ lấy vùng hợp lệ để không bị nhiễu)
note("\n## 8. Quan hệ sơ bộ (chỉ xét 1000 <= price <= 150k)")
ok = df[(p >= config.PRICE_MIN) & (p <= config.PRICE_MAX)]
by_year = ok.groupby("year")["price"].agg(["median", "size"]).loc[1980:]
med_year = by_year[by_year["size"] >= 300]["median"]   # bỏ năm quá ít tin (vd 2022 chỉ ~130 tin) để đường không bị nhiễu
fig, ax = pu.plt.subplots(figsize=(8, 3.8))
ax.plot(med_year.index, med_year.values, color=pu.BLUE, linewidth=2)
ax.set_title("Giá trung vị theo năm sản xuất (dữ liệu gốc)", loc="left")
ax.yaxis.set_major_formatter(pu.usd)
ax.axvline(config.YEAR_MIN, color=pu.ORANGE, linestyle="--", linewidth=1.5)
ax.text(config.YEAR_MIN, med_year.max(), " YEAR_MIN: trước mốc này giá tăng theo tuổi (xe cổ)",
        color=pu.ORANGE, fontsize=8, va="top")
pu.save(fig, OUT / "10_price_by_year_raw.png")
note("- Giá trung vị giảm dần khi xe cũ hơn, nhưng xe trước ~1990 giá lại TĂNG (xe sưu tầm)")

desc_num = df[["price", "year", "odometer", "lat", "long"]].describe(
    percentiles=[.01, .05, .25, .5, .75, .95, .99]).T
desc_num.to_csv(OUT / "numeric_describe.csv", encoding="utf-8-sig")

(OUT / "summary_raw.md").write_text("\n".join(lines), encoding="utf-8")
print(f"\n==> Xong. Xem toàn bộ kết quả trong: {OUT}")
