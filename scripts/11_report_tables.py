"""
11_report_tables.py - BẢNG SỐ LIỆU BỔ SUNG CHO BÁO CÁO (chỉ đọc dữ liệu, không sửa gì)

  1. Thống kê mô tả các biến số trên dữ liệu sạch          -> reports/descriptive_stats.csv
  2. Cơ cấu dữ liệu trước và sau làm sạch (kiểm tra việc
     loại 53,5% số dòng có làm lệch phân bố hay không)    -> reports/composition_before_after.csv
  3. 'unknown' có mang thông tin không: tỷ lệ bỏ trống theo
     loại người bán và giá tương đối của tin bỏ trống      -> reports/unknown_vs_known.csv

Chạy: python 11_report_tables.py   (khoảng 1 phút)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # thư mục gốc repo
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import pandas as pd

from src import config
from src.data_loader import load_clean, load_raw

R = config.REPORT_DIR
df = load_clean()

# 1. Thống kê mô tả ------------------------------------------------------------------------
num = ["price", "year", "car_age", "odometer", "miles_per_year", "desc_len"]
desc = df[num].describe(percentiles=[0.25, 0.5, 0.75]).T
desc["skew"] = df[num].skew()
desc = desc.rename(columns={"count": "n", "mean": "trung_binh", "std": "do_lech_chuan", "min": "min",
                            "25%": "q1", "50%": "trung_vi", "75%": "q3", "max": "max", "skew": "do_lech"})
desc.round(2).to_csv(R / "descriptive_stats.csv", encoding="utf-8-sig")
print("1. Thống kê mô tả\n", desc.round(1).to_string())

# 2. Cơ cấu trước / sau làm sạch -------------------------------------------------------------
raw = load_raw(usecols=["id", "url", "price", "year", "odometer", "manufacturer", "type", "state"])
raw["seller_type"] = raw["url"].str.extract(r"/(ct[od])/")[0].map({"ctd": "dealer", "cto": "owner"})


def profile(d, name):
    t = d["type"].fillna("unknown").str.lower()
    return {"tap": name, "so_dong": len(d),
            "pct_dai_ly": (d["seller_type"] == "dealer").mean() * 100,
            "nam_trung_vi": d["year"].median(),
            "odometer_trung_vi": d["odometer"].median(),
            "gia_trung_vi_gia_duong": d.loc[d["price"] > 0, "price"].median(),
            "pct_pickup_truck": t.isin(["pickup", "truck"]).mean() * 100,
            "pct_sedan": (t == "sedan").mean() * 100,
            "pct_suv": (t == "suv").mean() * 100,
            "pct_top5_bang": d["state"].value_counts(normalize=True).head(5).sum() * 100}


comp = pd.DataFrame([profile(raw, "goc"), profile(df, "sach")])
comp.round(2).to_csv(R / "composition_before_after.csv", index=False, encoding="utf-8-sig")
print("\n2. Cơ cấu trước / sau làm sạch\n", comp.round(1).T.to_string())

# 3. 'unknown' có mang thông tin không? ---------------------------------------------------------
grp = df.groupby(["make_model", "year"])["price"]
rel = (df["price"] / grp.transform("median")).where(grp.transform("size") >= 10)
rows = []
for c in ["condition", "cylinders", "drive", "type", "paint_color"]:
    unk = df[c] == "unknown"
    rows.append({"cot": c,
                 "pct_unknown_dai_ly": unk[df["seller_type"] == "dealer"].mean() * 100,
                 "pct_unknown_chinh_chu": unk[df["seller_type"] == "owner"].mean() * 100,
                 "gia_tuong_doi_unknown": rel[unk].median(),
                 "gia_tuong_doi_co_khai": rel[~unk].median()})
uk = pd.DataFrame(rows)
uk.round(3).to_csv(R / "unknown_vs_known.csv", index=False, encoding="utf-8-sig")
print("\n3. Tin bỏ trống thông số\n", uk.round(3).to_string(index=False))
