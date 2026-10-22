"""
09_fill_experiment.py - THÍ NGHIỆM: ĐIỀN DỮ LIỆU THIẾU CÓ GIÚP MÔ HÌNH DỰ BÁO GIÁ TỐT HƠN?

Cùng một cách chia train/test (80/20, random_state=42), so sánh 4 cấu hình dữ liệu:
  A  Gốc          : 5 cột thông số giữ 'unknown' như dữ liệu sạch
  B  + VIN        : điền 'unknown' bằng thông tin tra từ VIN
  C  + VIN + nhóm : B rồi điền tiếp bằng giá trị phổ biến của nhóm xe (GroupModeImputer
                    FIT TRÊN TẬP TRAIN, áp cho test -> không rò rỉ dữ liệu)
  D  C + đặc trưng VIN mới : thêm dung tích máy, mã lực, số cửa, phiên bản (trim)
với 2 mô hình: Ridge (tuyến tính) và HistGradientBoosting (cây tăng cường).

Chạy: python 09_fill_experiment.py            (cả 4 cấu hình)
      python 09_fill_experiment.py A B        (chỉ chạy A và B; kết quả cũ được giữ)
Kết quả: reports/fill_experiment.csv
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
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

from src import config
from src.features import GroupModeImputer, build_preprocessor, get_feature_lists

SPEC = ["drive", "cylinders", "type", "fuel", "transmission"]
RESULT_CSV = config.REPORT_DIR / "fill_experiment.csv"
CONFIG_NAMES = {"A": "Gốc (giữ unknown)", "B": "+ VIN", "C": "+ VIN + nhóm (fit trên train)",
                "D": "C + đặc trưng VIN mới"}


def cyl_num(s):
    return pd.to_numeric(s.astype(str).str.extract(r"(\d+)")[0], errors="coerce")


def make_config(df, tr_idx, te_idx, name):
    """Trả về (X_train, X_test, numeric, categorical, high_card) cho một cấu hình."""
    d = df.copy()
    if name in ("B", "C", "D"):
        for c in SPEC:          # chỉ lấy giá trị từ người bán + VIN, bỏ phần điền theo nhóm của file 08
            d[c] = d[f"{c}_filled"].where(d[f"{c}_source"].isin(["listing", "vin"]), "unknown")
    tr, te = d.loc[tr_idx].copy(), d.loc[te_idx].copy()
    if name in ("C", "D"):
        gm = GroupModeImputer(SPEC).fit(tr)                    # học CHỈ trên train
        tr, te = gm.transform(tr), gm.transform(te)
    for part in (tr, te):
        part["cylinders_num"] = cyl_num(part["cylinders"])
    num, cat, high = get_feature_lists(df)
    num = [c for c in num if not c.startswith("vin_")]
    if name == "D":
        num = num + ["vin_displacement_l", "vin_engine_hp", "vin_doors", "vin_decoded"]
        for part in (tr, te):
            part["make_model_trim"] = (part["make_model"] + " | " + part["vin_trim"].fillna("?")).where(
                part["vin_trim"].notna(), "no-trim")
        high = high + ["make_model_trim"]
    return tr, te, num, cat, high


def ridge_pipe(num, cat, high):
    return Pipeline([("prep", build_preprocessor(num, cat, high)), ("model", Ridge(alpha=1.0))])


def hgb_pipe(num, cat, high):
    # HGB tự xử lý NaN ở biến số nên không cần điền trung vị
    enc = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1,
                         encoded_missing_value=-1, max_categories=250)
    prep = ColumnTransformer([("cat", enc, cat + high), ("num", "passthrough", num)])
    n_cat = len(cat) + len(high)
    model = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.1, max_leaf_nodes=63,
                                          categorical_features=list(range(n_cat)),
                                          random_state=config.RANDOM_STATE)
    return Pipeline([("prep", prep), ("model", model)])


def main(selected):
    df = pd.read_pickle(config.PROCESSED_DIR / "vehicles_filled.pkl")
    idx_tr, idx_te = train_test_split(df.index, test_size=0.2, random_state=config.RANDOM_STATE)
    y_tr, y_te = df.loc[idx_tr, "log_price"], df.loc[idx_te, "log_price"]
    old = pd.read_csv(RESULT_CSV) if RESULT_CSV.exists() else pd.DataFrame()
    rows = []
    for name in selected:
        tr, te, num, cat, high = make_config(df, idx_tr, idx_te, name)
        unk = {c: round((te[c] == "unknown").mean() * 100, 1) for c in SPEC}
        print(f"\n[{name}] {CONFIG_NAMES[name]} | % unknown trên test: {unk}")
        for mname, builder in (("Ridge", ridge_pipe), ("HistGradientBoosting", hgb_pipe)):
            t0 = time.time()
            pipe = builder(num, cat, high)
            pipe.fit(tr[num + cat + high], y_tr)
            pred = pipe.predict(te[num + cat + high])
            mae = mean_absolute_error(np.expm1(y_te), np.expm1(pred))
            r2 = r2_score(y_te, pred)
            print(f"   {mname:22s} R2(log) = {r2:.4f} | MAE = ${mae:,.0f} | {time.time() - t0:.0f}s", flush=True)
            rows.append({"cau_hinh": name, "mo_ta": CONFIG_NAMES[name], "mo_hinh": mname,
                         "r2_log": round(r2, 4), "mae_usd": round(mae), "giay": round(time.time() - t0),
                         **{f"unknown_{c}_pct": v for c, v in unk.items()}})
    new = pd.DataFrame(rows)
    if len(old):
        old = old[~old["cau_hinh"].isin(selected)]
    res = pd.concat([old, new]).sort_values(["mo_hinh", "cau_hinh"])
    res.to_csv(RESULT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n==> Đã lưu {RESULT_CSV}")
    print(res[["cau_hinh", "mo_ta", "mo_hinh", "r2_log", "mae_usd"]].to_string(index=False))


if __name__ == "__main__":
    sel = [a.upper() for a in sys.argv[1:]] or ["A", "B", "C", "D"]
    main(sel)
