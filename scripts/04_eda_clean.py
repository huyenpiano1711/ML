"""
04_eda_clean.py - EDA TRÊN DỮ LIỆU ĐÃ LÀM SẠCH

Trả lời các câu hỏi phục vụ mô hình và đề xuất tính năng:
  1. Biến mục tiêu nên dùng price hay log(price)?
  2. Xe mất giá theo tuổi / số dặm như thế nào? (đường cong khấu hao)
  3. Biến phân loại nào ảnh hưởng mạnh tới giá?
  4. Các cờ từ khóa trong mô tả (một chủ, bảo hành, cần sửa...) có làm giá khác đi không?
     -> dùng "giá tương đối" = giá / giá trung vị của xe cùng hãng + dòng + năm,
        để so sánh công bằng (không bị lẫn hiệu ứng xe mới/xe sang).
  5. Đại lý vs chính chủ, bang nào rẻ/đắt hơn?

Kết quả: reports/eda_clean/*.png, *.csv, summary_clean.md
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
from src.data_loader import load_clean

OUT = config.EDA_CLEAN_DIR
lines = []


def note(t=""):
    print(t)
    lines.append(t)


df = load_clean()
N = len(df)
note("# EDA dữ liệu sạch\n")
note(f"- {N:,} dòng x {df.shape[1]} cột; {df['make_model'].nunique():,} cặp hãng+dòng xe, "
     f"{df['manufacturer'].nunique()} hãng")

# Giá tương đối so với xe cùng hãng + dòng + năm (chỉ tính cho nhóm >= 10 xe)
grp = df.groupby(["make_model", "year"])["price"]
df["grp_n"] = grp.transform("size")
df["rel_price"] = (df["price"] / grp.transform("median")).where(df["grp_n"] >= 10)
note(f"- {df['rel_price'].notna().mean() * 100:.1f}% số dòng thuộc nhóm hãng+dòng+năm có >= 10 xe "
     "(dùng để tính giá tương đối)")

# 1. BIẾN MỤC TIÊU --------------------------------------------------------------
note("\n## 1. Biến mục tiêu")
skew_p, skew_lp = df["price"].skew(), df["log_price"].skew()
note(f"- Độ lệch (skewness): price = {skew_p:.2f}, log(1+price) = {skew_lp:.2f} "
     "-> nên train trên log_price rồi đổi ngược bằng expm1")
pu.hist(df["price"], "Giá sau làm sạch - vẫn lệch phải", OUT / "01_price_hist.png",
        xlabel="Giá (USD)", fmt=pu.usd)
pu.hist(df["log_price"], "log(1 + giá) - gần phân phối chuẩn hơn", OUT / "02_log_price_hist.png",
        xlabel="log(1 + giá)")

# 2. KHẤU HAO ---------------------------------------------------------------------
note("\n## 2. Khấu hao theo tuổi và số dặm")
by_age = df.groupby("car_age")["price"].describe(percentiles=[.25, .5, .75])
by_age = by_age[by_age["count"] >= 200]
fig, ax = pu.plt.subplots(figsize=(8, 4))
ax.fill_between(by_age.index, by_age["25%"], by_age["75%"], color=pu.BLUE, alpha=0.15,
                linewidth=0, label="25%-75%")
ax.plot(by_age.index, by_age["50%"], color=pu.BLUE, linewidth=2, label="Trung vị")
ax.set_title("Giá theo tuổi xe (trung vị và khoảng 25%-75%)", loc="left")
ax.set_xlabel("Tuổi xe (năm)")
ax.yaxis.set_major_formatter(pu.usd)
ax.legend(frameon=False)
pu.save(fig, OUT / "03_price_by_age.png")
y1 = by_age["50%"]
note("- Giá trung vị theo tuổi: " + ", ".join(f"{a:.0f} năm: ${v:,.0f}" for a, v in y1.iloc[::3].items()))
by_age[["count", "25%", "50%", "75%"]].to_csv(OUT / "price_by_age.csv", encoding="utf-8-sig")

# Đường khấu hao của 4 dòng xe phổ biến (giá trị giữ lại so với xe 1 tuổi)
top4 = df["make_model"].value_counts().index[:4].tolist()
fig, ax = pu.plt.subplots(figsize=(8, 4))
colors = [pu.BLUE, pu.ORANGE, pu.AQUA, pu.YELLOW]
for mm, col in zip(top4, colors):
    s = df[df["make_model"] == mm].groupby("car_age")["price"].agg(["median", "size"])
    s = s[(s["size"] >= 30) & (s.index <= 20)]["median"]
    base = s.loc[s.index[s.index >= 1][0]]
    ret = s / base * 100
    ax.plot(ret.index, ret.values, color=col, linewidth=2, label=mm)
    note(f"- {mm}: sau 5 năm còn ~{ret.get(5, np.nan):.0f}%, sau 10 năm còn ~{ret.get(10, np.nan):.0f}% giá trị (so với xe 1 tuổi)")
ax.set_title("Tỷ lệ giữ giá so với xe 1 tuổi - 4 dòng xe phổ biến nhất", loc="left")
ax.set_xlabel("Tuổi xe (năm)")
ax.set_ylabel("% giá trị còn lại")
ax.set_xlim(0, 20.5)
ax.legend(frameon=False)
pu.save(fig, OUT / "04_depreciation_top4.png")

fig, ax = pu.plt.subplots(figsize=(8, 4))
hb = ax.hexbin(df["odometer"], df["price"], gridsize=60, bins="log", cmap="Blues", mincnt=1)
ax.set_title("Giá theo số dặm đã đi (mật độ, thang log)", loc="left")
ax.set_xlabel("Số dặm")
ax.xaxis.set_major_formatter(pu.thousands)
ax.yaxis.set_major_formatter(pu.usd)
fig.colorbar(hb, ax=ax, label="Số tin (log)")
pu.save(fig, OUT / "05_price_vs_odometer.png")

# 3. TƯƠNG QUAN BIẾN SỐ -----------------------------------------------------------
note("\n## 3. Tương quan Spearman với giá")
num_cols = ["car_age", "odometer", "miles_per_year", "cylinders_num", "condition_rank", "lat", "long",
            "n_unknown_specs", "desc_len", "has_vin", "posting_dow"]
num_cols = [c for c in num_cols if c in df.columns]
corr = df[num_cols + ["price"]].corr(method="spearman")
corr.round(3).to_csv(OUT / "spearman_corr.csv", encoding="utf-8-sig")
cp = corr["price"].drop("price").sort_values()
note(cp.round(3).to_string())
fig, ax = pu.plt.subplots(figsize=(8, 4))
ax.barh(cp.index, cp.values, color=[pu.ORANGE if v < 0 else pu.BLUE for v in cp.values], height=0.65)
ax.axvline(0, color=pu.TEXT_2, linewidth=0.8)
ax.set_title("Tương quan Spearman giữa các biến số và giá", loc="left")
ax.grid(axis="y", visible=False)
for i, v in enumerate(cp.values):
    ax.text(v + (0.02 if v >= 0 else -0.02), i, f"{v:.2f}", va="center",
            ha="left" if v >= 0 else "right", fontsize=8, color=pu.TEXT_2)
ax.set_xlim(-1, 1)
pu.save(fig, OUT / "06_spearman_price.png")

fig, ax = pu.plt.subplots(figsize=(7.5, 6))
im = ax.imshow(corr.values, cmap="RdBu", vmin=-1, vmax=1)
ax.set_xticks(range(len(corr)), corr.columns, rotation=60, ha="right")
ax.set_yticks(range(len(corr)), corr.columns)
ax.grid(False)
for i in range(len(corr)):
    for j in range(len(corr)):
        ax.text(j, i, f"{corr.values[i, j]:.2f}", ha="center", va="center", fontsize=6.5,
                color="white" if abs(corr.values[i, j]) > 0.6 else pu.TEXT)
fig.colorbar(im, ax=ax, shrink=0.8)
ax.set_title("Ma trận tương quan Spearman", loc="left")
pu.save(fig, OUT / "07_corr_matrix.png")

# 4. BIẾN PHÂN LOẠI ----------------------------------------------------------------
note("\n## 4. Giá trung vị theo biến phân loại")
cat_cols = ["type", "condition", "fuel", "drive", "transmission", "title_status", "seller_type",
            "brand_tier", "cylinders", "paint_color"]
cat_rows = []
for c in cat_cols:
    st = df.groupby(c).agg(so_tin=("price", "size"), gia_trung_vi=("price", "median"),
                           gia_tuong_doi=("rel_price", "median"))
    st = st[st["so_tin"] >= 100]
    for k, r in st.iterrows():
        cat_rows.append({"bien": c, "gia_tri": k, **r.to_dict()})
    pu.barh(st["gia_trung_vi"], f"Giá trung vị theo {c}", OUT / f"08_median_by_{c}.png",
            xlabel="Giá trung vị (USD)", fmt=pu.usd)
    note(f"- {c}: " + ", ".join(f"{k} ${v:,.0f}" for k, v in st["gia_trung_vi"].sort_values(ascending=False).items()))
pd.DataFrame(cat_rows).to_csv(OUT / "median_price_by_category.csv", index=False, encoding="utf-8-sig")

mf = df.groupby("manufacturer")["price"].agg(["median", "size"])
mf = mf[mf["size"] >= 300]["median"].sort_values(ascending=False).head(25)
pu.barh(mf, "Giá trung vị theo hãng (top 25, hãng có >= 300 tin)", OUT / "09_median_by_manufacturer.png",
        xlabel="Giá trung vị (USD)", fmt=pu.usd)

# 5. ĐẠI LÝ vs CHÍNH CHỦ (so sánh trong cùng nhóm xe) -------------------------------
note("\n## 5. Đại lý vs chính chủ (giá tương đối trong cùng hãng+dòng+năm)")
so = df.groupby("seller_type")["rel_price"].median()
note(f"- Giá tương đối trung vị: dealer {so.get('dealer', np.nan):.3f}, owner {so.get('owner', np.nan):.3f} "
     f"-> cùng một mẫu xe, đại lý niêm yết cao hơn chính chủ khoảng {(so['dealer'] / so['owner'] - 1) * 100:.0f}%")
own = df.groupby("seller_type")[["odometer", "car_age"]].median()
note(f"- (Lưu ý: xe đại lý có odometer trung vị {own.loc['dealer', 'odometer']:,.0f} so với "
     f"{own.loc['owner', 'odometer']:,.0f} của chính chủ -> một phần chênh lệch đến từ số dặm)")

# 6. TỪ KHÓA TRONG MÔ TẢ ------------------------------------------------------------
# Chênh lệch = trung vị giá tương đối của tin CÓ từ khóa / của tin KHÔNG có - 1.
# Khoảng tin cậy 95% bằng bootstrap (lấy mẫu lại có hoàn lại từng nhóm, 300 lần).
# Tính thêm riêng cho tin chính chủ và tin đại lý, vì nhiều từ khóa (vd "financing")
# gần như chỉ đại lý dùng -> chênh lệch chung có thể chỉ là chênh lệch đại lý / chính chủ.
KW_LABELS = {"kw_one_owner": "Một chủ", "kw_clean_history": "Lịch sử sạch", "kw_warranty": "Bảo hành",
             "kw_financing": "Hỗ trợ trả góp", "kw_needs_work": "Cần sửa / không chạy",
             "kw_new_tires": "Lốp mới", "kw_leather": "Ghế da", "kw_sunroof": "Cửa sổ trời",
             "kw_navigation": "Định vị", "kw_backup_camera": "Camera lùi", "kw_lifted": "Nâng gầm",
             "kw_low_miles": "Ít dặm"}
N_BOOT = 300


def kw_gap(rel, flag, rng=None):
    """(chênh lệch %, CI thấp, CI cao, số tin có từ khóa) cho một cờ từ khóa."""
    a, b = rel[flag == 1], rel[flag == 0]
    if len(a) < 30:
        return np.nan, np.nan, np.nan, len(a)
    est = (np.median(a) / np.median(b) - 1) * 100
    if rng is None:
        return est, np.nan, np.nan, len(a)
    boots = [(np.median(rng.choice(a, len(a))) / np.median(rng.choice(b, len(b))) - 1) * 100
             for _ in range(N_BOOT)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return est, lo, hi, len(a)


kw = [c for c in df.columns if c.startswith("kw_")]
if kw:
    note("\n## 6. Ảnh hưởng của từ khóa trong mô tả (giá tương đối có / không có từ khóa)")
    rng = np.random.default_rng(config.RANDOM_STATE)
    base = df[df["rel_price"].notna()]
    rel = base["rel_price"].to_numpy()
    rows = []
    for c in kw:
        flag = base[c].to_numpy()
        est, lo, hi, n_co = kw_gap(rel, flag, rng)
        row = {"tu_khoa": c, "nhan": KW_LABELS.get(c, c), "so_tin_co": n_co,
               "pct_tin_co": flag.mean() * 100, "pct_tin_dai_ly": base.loc[flag == 1, "seller_type"].eq("dealer").mean() * 100,
               "chenh_lech_pct": est, "ci95_thap": lo, "ci95_cao": hi}
        for st in ("owner", "dealer"):
            m = (base["seller_type"] == st).to_numpy()
            row[f"chenh_lech_{st}_pct"] = kw_gap(rel[m], flag[m])[0]
        rows.append(row)
    kwdf = pd.DataFrame(rows).sort_values("chenh_lech_pct")
    kwdf.round(3).to_csv(OUT / "keyword_effect.csv", index=False, encoding="utf-8-sig")
    note(f"- Tính trên {len(base):,} tin thuộc nhóm hãng+dòng+năm có >= 10 xe; CI 95% bootstrap {N_BOOT} lần")
    note(kwdf.drop(columns="tu_khoa").round(2).to_string(index=False))

    vn = lambda n: f"{n:,}".replace(",", ".")
    fig, (ax, ax2) = pu.plt.subplots(1, 2, figsize=(10.5, 5.2), sharey=True,
                                     gridspec_kw={"width_ratios": [1.35, 1], "wspace": 0.08})
    v = kwdf["chenh_lech_pct"].to_numpy()
    lo, hi = kwdf["ci95_thap"].to_numpy(), kwdf["ci95_cao"].to_numpy()
    y = np.arange(len(kwdf))
    # (a) toàn bộ tin, kèm khoảng tin cậy 95%
    ax.barh(y, v, color=[pu.ORANGE if x < 0 else pu.BLUE for x in v], height=0.62)
    ax.errorbar(v, y, xerr=np.vstack([v - lo, hi - v]), fmt="none", ecolor=pu.TEXT, elinewidth=0.9, capsize=2.5)
    for i, x in enumerate(v):
        edge = hi[i] if x >= 0 else lo[i]
        ax.text(edge + (0.8 if x >= 0 else -0.8), i, f"{x:+.1f}%".replace(".", ","), va="center",
                ha="left" if x >= 0 else "right", fontsize=8, color=pu.TEXT_2)
    ax.set_yticks(y, [f"{r.nhan} ({vn(r.so_tin_co)} tin)" for r in kwdf.itertuples()])
    ax.axvline(0, color=pu.TEXT_2, linewidth=0.8)
    ax.set_xlim(-62, 22)
    ax.set_title("(a) Toàn bộ tin, thanh lỗi = KTC 95% bootstrap", loc="left", fontsize=10)
    ax.set_xlabel("% chênh lệch trung vị giá tương đối")
    ax.grid(axis="y", visible=False)
    # (b) tách theo loại người bán: kiểm tra yếu tố gây nhiễu
    for col, mk, colr, lab in (("chenh_lech_owner_pct", "D", pu.ORANGE, "Chính chủ"),
                               ("chenh_lech_dealer_pct", "o", pu.BLUE, "Đại lý")):
        ax2.scatter(kwdf[col], y, marker=mk, s=30, color=colr, zorder=3, label=lab)
    for i, (o, d) in enumerate(zip(kwdf["chenh_lech_owner_pct"], kwdf["chenh_lech_dealer_pct"])):
        ax2.plot([o, d], [i, i], color=pu.GRID, linewidth=2, zorder=2)
    ax2.axvline(0, color=pu.TEXT_2, linewidth=0.8)
    ax2.set_xlim(-55, 28)
    ax2.set_title("(b) Tính riêng trong từng loại người bán", loc="left", fontsize=10)
    ax2.set_xlabel("% chênh lệch trung vị giá tương đối")
    ax2.grid(axis="y", visible=False)
    ax2.legend(loc="lower right", fontsize=8, frameon=False)
    fig.suptitle("Chênh lệch giá tương đối khi mô tả có từ khóa (so với xe cùng hãng + dòng + năm)",
                 x=0.01, ha="left", fontsize=11.5, fontweight="bold")
    pu.save(fig, OUT / "10_keyword_effect.png")

# 7. ĐỊA LÝ ----------------------------------------------------------------------------
note("\n## 7. Bang rẻ / đắt nhất (giá tương đối trung vị, bang có >= 1000 tin)")
stt = df.groupby("state")["rel_price"].agg(["median", "size"])
stt = stt[stt["size"] >= 1000]["median"].sort_values()
stt.to_csv(OUT / "state_relative_price.csv", encoding="utf-8-sig")
note("- Rẻ nhất: " + ", ".join(f"{k.upper()} {v:.3f}" for k, v in stt.head(5).items()))
note("- Đắt nhất: " + ", ".join(f"{k.upper()} {v:.3f}" for k, v in stt.tail(5).items()))
pu.barh(((stt - 1) * 100).rename(index=str.upper),"Giá tương đối theo bang (% so với trung vị toàn quốc cùng mẫu xe)",
        OUT / "11_state_relative_price.png", xlabel="% chênh lệch",
        fmt=pu.mticker.FuncFormatter(lambda x, _: f"{x:+.1f}%"), annotate=False)

# 8. MỨC ĐỘ "unknown" CÒN LẠI ------------------------------------------------------------
note("\n## 8. Tỷ lệ 'unknown' còn lại ở biến phân loại")
unk = pd.Series({c: (df[c] == "unknown").mean() * 100 for c in
                 ["condition", "cylinders", "drive", "type", "paint_color", "fuel", "title_status", "transmission"]})
note(unk.round(2).to_string())
pu.barh(unk, "Tỷ lệ 'unknown' sau làm sạch (%)", OUT / "12_unknown_share.png", xlabel="%",
        fmt=pu.mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))

(OUT / "summary_clean.md").write_text("\n".join(lines), encoding="utf-8")
print(f"\n==> Xong. Kết quả trong: {OUT}")
