"""
14_feature_check.py - A04: KIỂM CHỨNG BỘ THUỘC TÍNH ĐÃ CHỌN BẰNG SỐ LIỆU

Câu hỏi: bỏ các cột người dùng KHÔNG nhập được trên form (mô tả tin, VIN, tọa độ, loại người bán...)
thì mô hình dự đoán giá kém đi bao nhiêu? Và nếu người dùng bỏ trống các ô "Tùy chọn nâng cao"?

Cùng một mô hình (HistGradientBoosting, tham số giống 09_fill_experiment.py), học trên TẬP TRAIN,
đánh giá trên TẬP VALIDATION (không dùng tập test - tập test để dành cho B04):
  M0  Mốc ngây thơ          : luôn đoán giá trung vị của tập train (DummyRegressor)
  F0  Toàn bộ cột           : bộ cột của cấu hình C trong 09_fill_experiment.py (có desc_len, kw_*, lat/long...)
  F1  Chỉ cột trên form     : 17 cột trong feature_schema.json, người dùng điền đủ mọi ô
  F2  Form, bỏ trống nâng cao: như F1 nhưng ở tập validation 5 ô nâng cao để trống -> xử lý đúng như app
                               (drive, cylinders: GroupModeImputer; paint_color: unknown;
                                title_status, state: giá trị mặc định trong schema)

Đầu vào : data/processed/vehicles_filled.pkl, data/splits/*.csv, src/features/feature_schema.json
Đầu ra  : reports/feature_selection.csv

Chạy: python 14_feature_check.py   (chạy SAU 12_split_data.py và 13_build_feature_schema.py)
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

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, median_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

from src import config
from src.features import GroupModeImputer, get_feature_lists
from src.features.preprocessing import CONDITION_ORDER

SPEC = ["drive", "cylinders", "type", "fuel", "transmission"]
SCHEMA_JSON = config.PROJECT_DIR / "src" / "features" / "feature_schema.json"
SPLIT_DIR = config.DATA_DIR / "splits"
OUT_CSV = config.REPORT_DIR / "feature_selection.csv"
NAMES = {"M0": "Mốc: luôn đoán giá trung vị", "F0": "Toàn bộ cột (cấu hình C của 09)",
         "F1": "Chỉ cột trên form, điền đủ", "F2": "Chỉ cột trên form, bỏ trống 5 ô nâng cao"}


def derived(d):
    """Tính lại các cột phụ thuộc vào thông số sau khi điền (cùng công thức add_features)."""
    d["cylinders_num"] = pd.to_numeric(d["cylinders"].astype(str).str.extract(r"(\d+)")[0], errors="coerce")
    d["condition_rank"] = d["condition"].map(CONDITION_ORDER)
    return d


def hgb_pipe(num, cat):
    enc = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1,
                         encoded_missing_value=-1, max_categories=250)
    prep = ColumnTransformer([("cat", enc, cat), ("num", "passthrough", num)])
    model = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.1, max_leaf_nodes=63,
                                          categorical_features=list(range(len(cat))),
                                          random_state=config.RANDOM_STATE)
    return Pipeline([("prep", prep), ("model", model)])


def metrics(name, y_log, pred_log, n_cols, secs):
    y, p = np.expm1(y_log), np.expm1(pred_log)
    return {"cau_hinh": name, "mo_ta": NAMES[name], "so_cot": n_cols,
            "mae_usd": round(mean_absolute_error(y, p)),
            "medae_usd": round(median_absolute_error(y, p)),
            "rmse_usd": round(float(np.sqrt(mean_squared_error(y, p)))),
            "r2_log": round(r2_score(y_log, pred_log), 4),
            "mape_pct": round(float(np.mean(np.abs(p - y) / y) * 100), 2),
            "giay": round(secs)}


def main():
    schema = json.loads(SCHEMA_JSON.read_text(encoding="utf-8"))
    defaults = {f["name"]: f.get("default") for f in schema["features"]}
    df = pd.read_pickle(config.PROCESSED_DIR / "vehicles_filled.pkl")
    for c in SPEC:      # giá trị người bán + VIN; phần điền theo nhóm sẽ học lại trên train
        df[c] = df[f"{c}_filled"].where(df[f"{c}_source"].isin(["listing", "vin"]), "unknown")
    ids = {k: pd.read_csv(SPLIT_DIR / f"{k}_ids.csv")["id"] for k in ("train", "val")}
    tr = df[df["id"].isin(ids["train"])].copy()
    va = df[df["id"].isin(ids["val"])].copy()

    gm = GroupModeImputer(SPEC).fit(tr)                      # học CHỈ trên train
    tr, va_full = derived(gm.transform(tr)), derived(gm.transform(va))
    y_tr, y_va = tr["log_price"], va_full["log_price"]

    # F2: mô phỏng người dùng bỏ trống 5 ô nâng cao ở tập validation
    va_blank = va.copy()
    va_blank[["drive", "cylinders", "paint_color"]] = "unknown"
    va_blank["title_status"] = defaults["title_status"]
    va_blank["state"] = defaults["state"]
    va_blank = derived(gm.transform(va_blank))

    rows = []
    t0 = time.time()
    dummy = DummyRegressor(strategy="median").fit(tr[["car_age"]], y_tr)
    rows.append(metrics("M0", y_va, dummy.predict(va_full[["car_age"]]), 0, time.time() - t0))

    num0, cat0, high0 = get_feature_lists(df)
    num0 = [c for c in num0 if not c.startswith("vin_")]
    cols = schema["price_model_columns"]
    num1, cat1 = cols["numeric"], cols["categorical"] + cols["high_cardinality"]

    for name, num, cat, val in (("F0", num0, cat0 + high0, va_full),
                                ("F1", num1, cat1, va_full),
                                ("F2", num1, cat1, va_blank)):
        t0 = time.time()
        if name != "F2":                        # F2 dùng lại mô hình của F1
            pipe = hgb_pipe(num, cat).fit(tr[num + cat], y_tr)
        pred = pipe.predict(val[num + cat])
        rows.append(metrics(name, y_va, pred, len(num + cat), time.time() - t0))
        print(f"[{name}] {NAMES[name]:42s} MAE = ${rows[-1]['mae_usd']:,} | R2(log) = {rows[-1]['r2_log']}",
              flush=True)

    # Bỏ trống TỪNG ô nâng cao một (các ô khác điền đủ) -> ô nào ảnh hưởng nhiều nhất
    blank_value = {"drive": "unknown", "cylinders": "unknown", "paint_color": "unknown",
                   "title_status": defaults["title_status"], "state": defaults["state"]}
    for col, v in blank_value.items():
        one = va.copy()
        one[col] = v
        one = derived(gm.transform(one))
        name = f"F2_{col}"
        NAMES[name] = f"Chỉ cột trên form, bỏ trống riêng ô {col}"
        rows.append(metrics(name, y_va, pipe.predict(one[num1 + cat1]), len(num1 + cat1), 0))

    res = pd.DataFrame(rows)
    res.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n==> Đã lưu {OUT_CSV} (đánh giá trên tập validation {len(va):,} dòng)")
    print(res.to_string(index=False))


if __name__ == "__main__":
    main()
