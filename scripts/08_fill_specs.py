"""
08_fill_specs.py - ĐIỀN THÔNG SỐ CÒN THIẾU (bài toán Completion) BẰNG VIN + NHÓM XE

Thứ tự ưu tiên cho 5 cột thông số kỹ thuật: drive, cylinders, type, fuel, transmission
  1. listing : giá trị người bán đã khai
  2. vin     : giá trị tra từ VIN qua NHTSA (dữ liệu của nhà sản xuất)
  3. group   : giá trị phổ biến nhất của nhóm hãng+dòng+năm (>= 10 xe, >= 90% giống nhau)
  4. unknown : còn lại giữ nguyên
KHÔNG điền condition, paint_color, title_status (đặc điểm riêng của từng chiếc xe).

Lưu ý về rò rỉ dữ liệu: bước 3 trong file này học trên TOÀN BỘ dữ liệu, chỉ dùng để hiển thị
và EDA. Khi train mô hình, bước 3 phải làm bằng GroupModeImputer fit trên tập train
(xem 09_fill_experiment.py). Bước 2 (VIN) là tra cứu bên ngoài nên không rò rỉ.

Đầu vào : data/processed/vehicles_clean.pkl, data/interim/vin_decoded.csv (từ 07_vin_decode.py)
Đầu ra  : data/processed/vehicles_filled.pkl/.csv
          reports/vin_agreement.csv   (VIN khớp với người bán tự khai bao nhiêu %)
          reports/fill_summary.csv    (% unknown trước/sau từng bước)
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
from src import vin_mapping as vm
from src.data_loader import load_clean
from src.features import GroupModeImputer

VIN_CSV = config.INTERIM_DIR / "vin_decoded.csv"
OUT_PKL = config.PROCESSED_DIR / "vehicles_filled.pkl"
OUT_CSV = config.PROCESSED_DIR / "vehicles_filled.csv"
SPEC_COLS = ["drive", "cylinders", "type", "fuel", "transmission"]
# Với 2 cột này, giá trị 'other' của người bán (chủ yếu tin đại lý) bị VIN thay thế nếu VIN rõ ràng
OVERRIDE_OTHER = {"fuel", "transmission"}
# Hãng ghi khác tên nhưng là một (Scion thuộc Toyota, Ram tách từ Dodge năm 2010...)
MAKE_ALIASES = {"scion": "toyota", "ram": "dodge"}


def norm_make(s):
    s = s.astype("string").str.lower().str.replace(r"[^a-z]", "", regex=True)
    return s.replace({k.replace("-", ""): v for k, v in MAKE_ALIASES.items()})


def main():
    df = load_clean()
    n0 = len(df)
    v = pd.read_csv(VIN_CSV, dtype=str, keep_default_na=False)
    v["id"] = v["id"].astype("int64")
    v = v[v["ErrorCode"].str.split(",").str[0] == "0"]          # chỉ dùng VIN giải mã đầy đủ
    df = df.merge(v.drop(columns=["VIN"]).add_prefix("v_").rename(columns={"v_id": "id"}),
                  on="id", how="left", validate="one_to_one")
    assert len(df) == n0
    has = df["v_ErrorCode"].notna()
    print(f"Tin có VIN giải mã đầy đủ: {int(has.sum()):,} / {n0:,} ({has.mean() * 100:.1f}%)")

    # --- 1. Quy đổi giá trị VIN về bộ giá trị của dataset ------------------------------------
    vin = pd.DataFrame(index=df.index)
    vin["drive"] = vm.map_drive(df["v_DriveType"])
    vin["cylinders"] = vm.map_cylinders(df["v_EngineCylinders"])
    vin["type"] = vm.map_type(df["v_BodyClass"])
    vin["fuel"] = vm.map_fuel(df["v_FuelTypePrimary"], df["v_ElectrificationLevel"])
    vin["transmission"] = vm.map_transmission(df["v_TransmissionStyle"])

    # '2wd' -> cầu trước hay cầu sau: tra theo dòng xe, dùng tin người bán đã khai fwd/rwd
    two = df[df["drive"].isin(["fwd", "rwd"])].groupby("make_model")["drive"].agg(
        n="size", top=lambda s: s.value_counts().index[0], share=lambda s: s.value_counts(normalize=True).iloc[0])
    two = two[(two["n"] >= 10) & (two["share"] >= 0.9)]["top"]
    is2 = vin["drive"] == "2wd"
    vin.loc[is2, "drive"] = df.loc[is2, "make_model"].map(two)
    print(f"VIN '4x2': {int(is2.sum()):,} tin, xác định được cầu trước/sau theo dòng xe: "
          f"{int(vin.loc[is2, 'drive'].notna().sum()):,}")

    # --- 2. Kiểm chứng: VIN khớp với người bán tự khai bao nhiêu? ---------------------------------
    rows = []
    for c in SPEC_COLS:
        both = df[c].ne("unknown") & df[c].ne("other") & vin[c].notna()
        agree = (df.loc[both, c] == vin.loc[both, c]).mean()
        rows.append({"cot": c, "so_tin_doi_chieu": int(both.sum()), "ty_le_khop_pct": round(agree * 100, 2)})
    agree_df = pd.DataFrame(rows)
    agree_df.to_csv(config.REPORT_DIR / "vin_agreement.csv", index=False, encoding="utf-8-sig")
    print("\nĐộ khớp VIN với thông tin người bán (trên các tin có cả hai):")
    print(agree_df.to_string(index=False))

    # Hãng và năm theo VIN có khớp tin đăng không -> cờ nghi khai sai
    mk_conf = has & (norm_make(df["v_Make"]) != norm_make(df["manufacturer"]))
    yr = pd.to_numeric(df["v_ModelYear"], errors="coerce")
    yr_conf = has & yr.notna() & (yr != df["year"])
    df["vin_make_conflict"] = mk_conf.astype("int8")
    df["vin_year_conflict"] = yr_conf.astype("int8")
    print(f"\nHãng theo VIN khác tin đăng: {int(mk_conf.sum()):,} tin | năm khác: {int(yr_conf.sum()):,} tin")

    # --- 3. Điền theo thứ tự ưu tiên ----------------------------------------------------------------
    summary = []
    for c in SPEC_COLS:
        df[f"{c}_filled"] = df[c].astype("object")
        src = np.where(df[c] != "unknown", "listing", "unknown").astype(object)
        fill = (df[c] == "unknown") & vin[c].notna() & ~mk_conf
        if c in OVERRIDE_OTHER:
            fill |= (df[c] == "other") & vin[c].notna() & ~mk_conf
        df.loc[fill, f"{c}_filled"] = vin.loc[fill, c]
        src[fill.to_numpy()] = "vin"
        df[f"{c}_source"] = src
        summary.append({"cot": c, "unknown_ban_dau_pct": (df[c] == "unknown").mean() * 100,
                        "dien_tu_vin": int(fill.sum())})

    gm = GroupModeImputer([f"{c}_filled" for c in SPEC_COLS])
    filled, srcs = gm.fit_transform(df[["make_model", "year"] + [f"{c}_filled" for c in SPEC_COLS]],
                                    return_source=True)
    for c, row in zip(SPEC_COLS, summary):
        g = srcs[f"{c}_filled"] == "group"
        df[f"{c}_filled"] = filled[f"{c}_filled"]
        df.loc[g, f"{c}_source"] = "group"
        row["dien_theo_nhom"] = int(g.sum())
        row["unknown_con_lai_pct"] = (df[f"{c}_filled"] == "unknown").mean() * 100

    # --- 4. Đặc trưng mới từ VIN ------------------------------------------------------------------------
    df["vin_trim"] = df["v_Trim"].str.strip().str.lower().replace({"": np.nan})
    df["vin_displacement_l"] = vm.to_number(df["v_DisplacementL"])
    df["vin_engine_hp"] = vm.to_number(df["v_EngineHP"])
    df["vin_doors"] = vm.to_number(df["v_Doors"])
    df["vin_decoded"] = has.astype("int8")
    df = df.drop(columns=[c for c in df.columns if c.startswith("v_")])

    # --- Kiểm tra chéo -----------------------------------------------------------------------------------
    assert len(df) == n0 and df["id"].is_unique
    for c in SPEC_COLS:
        keep = df[f"{c}_source"] == "listing"
        assert (df.loc[keep, c] == df.loc[keep, f"{c}_filled"]).all(), f"{c}: giá trị người bán bị thay đổi!"
        assert df[f"{c}_filled"].notna().all(), f"{c}_filled có NaN"
        assert ((df[f"{c}_filled"] == "unknown") == (df[f"{c}_source"] == "unknown")).all()
    assert (df.loc[df["vin_decoded"] == 0, [f"{c}_source" for c in SPEC_COLS]] != "vin").all().all()

    sm = pd.DataFrame(summary).round(2)
    sm.to_csv(config.REPORT_DIR / "fill_summary.csv", index=False, encoding="utf-8-sig")
    print("\nKết quả điền (% unknown trước -> sau):")
    print(sm.to_string(index=False))
    for c in SPEC_COLS:
        print(f"   {c:13s} nguồn: " + ", ".join(f"{k} {v:,}" for k, v in df[f'{c}_source'].value_counts().items()))
    print(f"   Có trim theo VIN: {df['vin_trim'].notna().sum():,} tin, {df['vin_trim'].nunique():,} giá trị")

    df.to_pickle(OUT_PKL)
    df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n==> Đã lưu {len(df):,} dòng x {df.shape[1]} cột -> {OUT_PKL.name}, {OUT_CSV.name}")


if __name__ == "__main__":
    main()
