"""
model_trainer.py - Huấn luyện, đánh giá và lưu mô hình dự đoán giá (dùng chung cho script và màn hình Admin).

Sửa theo bản review 08/11:
  - Dữ liệu chia theo nhóm xe, ngoại lai chỉ loại trên train (scripts/12_split_data.py).
  - Chọn mô hình theo MAE (USD) trên tập validation - đúng tiêu chí đã đặt ra.
  - Đánh giá theo ĐÚNG ĐƯỜNG CỦA ỨNG DỤNG: người dùng thường bỏ trống dẫn động, số xi-lanh, màu sơn
    nên app gửi "unknown". Khi huấn luyện, một phần xe được che 3 ô này thành "unknown" (augment_frac)
    để mô hình quen với trường hợp đó; khi đánh giá báo cả hai con số (đủ thông tin / bỏ trống 3 ô).
  - Khoảng giá "Likely price" lấy từ phân vị sai số TƯƠNG ĐỐI trên tập validation, tách theo 5 mức giá
    dự đoán (xe rẻ và xe đắt có sai số khác nhau), thay cho "± MAE" cố định.
  - Tập test chỉ dùng một lần trong scripts/19_train_final_model.py.

Pipeline lưu ra có cùng đầu vào với bản cũ (13 cột thô của form) nên Backend không phải đổi.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, median_absolute_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

from src import config
from src.features.preprocessing import (FeatureEngineer, GroupModeImputer, PRICE_MODEL_CATEGORICAL,
                                        PRICE_MODEL_HIGH_CARD, PRICE_MODEL_NUMERIC)

DATA_FILE = config.DATA_DIR / "processed" / "vehicles_filled.pkl"
SPLIT_DIR = config.DATA_DIR / "splits"
MODEL_DIR = config.PROJECT_DIR / "models" / "price_prediction"
REGISTRY_DIR = MODEL_DIR / "registry"
REGISTRY_FILE = MODEL_DIR / "registry.json"
ACTIVE_PIPELINE = MODEL_DIR / "final_pipeline.joblib"
METRICS_PATH = MODEL_DIR / "metrics.json"
METADATA_PATH = MODEL_DIR / "model_metadata.json"

RAW_INPUT_COLS = ["manufacturer", "model_base", "year", "type", "odometer", "condition", "fuel",
                  "transmission", "drive", "cylinders", "paint_color", "title_status", "state"]
SPEC_COLS = ["drive", "cylinders", "type", "fuel", "transmission"]
OPTIONAL_COLS = ["drive", "cylinders", "paint_color"]      # ô người dùng hay bỏ trống
INTERVAL_BINS = 5
INTERVAL_COVERAGE = 0.80                                   # khoảng chứa ~80% giá thật

# Thuật toán cho màn hình Admin: tên hiển thị, tham số mặc định, khoảng hợp lệ của từng tham số
ALGORITHMS = {
    "hgb": {"label": "HistGradientBoosting",
            "defaults": {"learning_rate": 0.08, "max_iter": 600, "max_leaf_nodes": 80, "min_samples_leaf": 25,
                         "l2_regularization": 0.5},
            "ranges": {"learning_rate": (0.01, 0.5), "max_iter": (50, 2000), "max_leaf_nodes": (8, 255),
                       "min_samples_leaf": (1, 500), "l2_regularization": (0.0, 10.0)}},
    "rf": {"label": "RandomForest",
           "defaults": {"n_estimators": 100, "max_depth": 22, "min_samples_leaf": 4},
           "ranges": {"n_estimators": (10, 500), "max_depth": (3, 60), "min_samples_leaf": (1, 200)}},
    "ridge": {"label": "Ridge Regression",
              "defaults": {"alpha": 10.0},
              "ranges": {"alpha": (0.0001, 1000.0)}},
    "dummy": {"label": "Dummy (median baseline)", "defaults": {}, "ranges": {}},
}
INT_PARAMS = {"max_iter", "max_leaf_nodes", "min_samples_leaf", "n_estimators", "max_depth"}


# ----------------------------------------------------------------------------------------- dữ liệu
def load_splits(data_file=DATA_FILE, split_dir=SPLIT_DIR):
    """(train, val, test) với các cột thô của form + price. Giá trị điền theo nhóm ở bước 08 được
    trả về "unknown" để GroupModeImputer trong pipeline học lại CHỈ trên train."""
    df = pd.read_pickle(data_file)
    for c in SPEC_COLS:
        df[c] = df[f"{c}_filled"].where(df[f"{c}_source"].isin(["listing", "vin"]), "unknown")
    keep = ["id"] + RAW_INPUT_COLS + ["price"]
    parts = []
    for name in ("train", "val", "test"):
        ids = pd.read_csv(Path(split_dir) / f"{name}_ids.csv")["id"]
        parts.append(as_numpy_dtypes(df.loc[df["id"].isin(ids), keep].reset_index(drop=True)))
    return tuple(parts)


def as_numpy_dtypes(df):
    """Kiểu dữ liệu numpy thuần (object / float64). Với pandas 3 + pyarrow, cột đọc từ pickle có thể là
    string[pyarrow] / double[pyarrow] dùng pandas.NA, làm ColumnTransformer của scikit-learn báo lỗi."""
    out = df.copy()
    for c in out.columns:
        if c in ("year", "odometer", "price"):
            out[c] = pd.to_numeric(out[c], errors="coerce").astype("float64")
        elif c != "id":
            out[c] = out[c].astype(object).where(out[c].notna(), "unknown")
    return out


def mask_optional(df, frac, seed=config.RANDOM_STATE):
    """Che 3 ô tùy chọn thành "unknown" ở một phần ngẫu nhiên các dòng (mô phỏng người dùng bỏ trống)."""
    if frac <= 0:
        return df
    out = df.copy()
    rows = np.random.default_rng(seed).random(len(out)) < frac
    out.loc[rows, OPTIONAL_COLS] = "unknown"
    return out


def app_view(df):
    """Dữ liệu như ứng dụng gửi khi người dùng để trống dẫn động, xi-lanh và màu sơn."""
    out = df.copy()
    out[OPTIONAL_COLS] = "unknown"
    return out


# ----------------------------------------------------------------------------------------- mô hình
def clean_params(algorithm, params=None):
    """Tham số hợp lệ cho thuật toán; báo ValueError (tiếng Việt) khi ngoài khoảng cho phép."""
    if algorithm not in ALGORITHMS:
        raise ValueError(f"Thuật toán không hỗ trợ: {algorithm}")
    spec = ALGORITHMS[algorithm]
    out = dict(spec["defaults"])
    for key, value in (params or {}).items():
        if key not in spec["defaults"]:
            continue
        value = int(value) if key in INT_PARAMS else float(value)
        lo, hi = spec["ranges"][key]
        if not lo <= value <= hi:
            raise ValueError(f"Tham số {key} phải nằm trong khoảng [{lo}; {hi}]")
        out[key] = value
    return out


def build_pipeline(algorithm="hgb", params=None, log_target=True, random_state=config.RANDOM_STATE):
    """Pipeline từ 13 cột thô -> giá USD: tạo đặc trưng -> điền theo nhóm (fit trên train) -> mã hóa -> hồi quy."""
    p = clean_params(algorithm, params)
    num, cat, high = PRICE_MODEL_NUMERIC, PRICE_MODEL_CATEGORICAL, PRICE_MODEL_HIGH_CARD
    if algorithm == "ridge":
        prep = ColumnTransformer([
            ("num", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), num),
            ("cat", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=25), cat),
            ("high", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=30), high)])
        reg = Ridge(alpha=p["alpha"])
    else:
        enc = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1, encoded_missing_value=-1,
                             max_categories=250)
        prep = ColumnTransformer([("cat", enc, cat + high), ("num", "passthrough", num)])
        if algorithm == "hgb":
            reg = HistGradientBoostingRegressor(categorical_features=list(range(len(cat + high))),
                                                random_state=random_state, **p)
        elif algorithm == "rf":
            reg = RandomForestRegressor(n_jobs=-1, random_state=random_state, **p)
        else:
            reg = DummyRegressor(strategy="median")
    pipe = Pipeline([("feature_eng", FeatureEngineer()), ("group_imputer", GroupModeImputer(cols=SPEC_COLS)),
                     ("prep", prep), ("reg", reg)])
    if log_target:
        return TransformedTargetRegressor(regressor=pipe, func=np.log1p, inverse_func=np.expm1)
    return pipe


def fit_model(train, algorithm="hgb", params=None, log_target=True, augment_frac=0.5):
    """Huấn luyện trên tập train (đã che ngẫu nhiên 3 ô tùy chọn) -> (pipeline, giây)."""
    t0 = time.time()
    data = mask_optional(train, augment_frac)
    pipe = build_pipeline(algorithm, params, log_target)
    pipe.fit(data[RAW_INPUT_COLS], data["price"].to_numpy(dtype=float))
    return pipe, time.time() - t0


def predict(pipe, df):
    return np.maximum(100.0, pipe.predict(df[RAW_INPUT_COLS]))


def compute_metrics(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    err = np.abs(y_true - y_pred)
    return {"mae_usd": round(float(mean_absolute_error(y_true, y_pred)), 2),
            "rmse_usd": round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 2),
            "medae_usd": round(float(median_absolute_error(y_true, y_pred)), 2),
            "p90_usd": round(float(np.percentile(err, 90)), 2),
            "r2_usd": round(float(r2_score(y_true, y_pred)), 4),
            "r2_log": round(float(r2_score(np.log1p(y_true), np.log1p(y_pred))), 4),
            "mape_pct": round(float(np.mean(err / y_true) * 100), 2),
            "sample_size": int(len(y_true))}


# ------------------------------------------------------------------------------------ khoảng giá
def fit_interval(y_true, y_pred, n_bins=INTERVAL_BINS, coverage=INTERVAL_COVERAGE):
    """Bảng khoảng giá theo mức giá dự đoán: với mỗi mức, tỷ lệ giá thật / giá dự đoán ở phân vị
    (1-coverage)/2 và (1+coverage)/2 trên tập validation (conformal đơn giản, tách theo mức giá)."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    edges = np.unique(np.quantile(y_pred, np.linspace(0, 1, n_bins + 1)[1:-1]))
    bins = np.searchsorted(edges, y_pred, side="right")
    ratio = y_true / y_pred
    lo_q, hi_q = (1 - coverage) / 2, (1 + coverage) / 2
    rows = []
    for b in range(len(edges) + 1):
        r = ratio[bins == b]
        if len(r) == 0:
            continue
        rows.append({"upper_pred_usd": None if b == len(edges) else round(float(edges[b]), 2),
                     "low_ratio": round(float(np.quantile(r, lo_q)), 4),
                     "high_ratio": round(float(np.quantile(r, hi_q)), 4), "n": int(len(r))})
    rows[-1]["upper_pred_usd"] = None
    return {"coverage": coverage, "bins": rows}


def apply_interval(pred, table):
    """(thấp, cao) cho một giá dự đoán theo bảng của fit_interval()."""
    for row in table["bins"]:
        if row["upper_pred_usd"] is None or pred <= row["upper_pred_usd"]:
            return max(100.0, pred * row["low_ratio"]), pred * row["high_ratio"]
    row = table["bins"][-1]
    return max(100.0, pred * row["low_ratio"]), pred * row["high_ratio"]


def interval_coverage(y_true, y_pred, table):
    lo_hi = np.array([apply_interval(p, table) for p in y_pred])
    y = np.asarray(y_true, dtype=float)
    inside = (y >= lo_hi[:, 0]) & (y <= lo_hi[:, 1])
    return round(float(inside.mean() * 100), 2), round(float(np.median(lo_hi[:, 1] - lo_hi[:, 0])), 2)


# ------------------------------------------------------------------------------- huấn luyện + đánh giá
def train_and_validate(algorithm="hgb", params=None, log_target=True, augment_frac=0.5, splits=None,
                       progress=None):
    """Dùng cho màn hình Admin: train trên train, đo trên val (đủ thông tin và đường app),
    tính bảng khoảng giá. Không đụng tới tập test. Trả về dict kết quả (kèm pipeline)."""
    say = progress or (lambda _msg: None)
    say("Đang nạp dữ liệu train/validation...")
    train, val, _test = splits or load_splits()
    say(f"Đang huấn luyện {ALGORITHMS[algorithm]['label']} trên {len(train):,} xe...")
    pipe, seconds = fit_model(train, algorithm, params, log_target, augment_frac)
    say("Đang đánh giá trên tập validation...")
    y_val = val["price"].to_numpy(dtype=float)
    pred_full = predict(pipe, val)
    pred_app = predict(pipe, app_view(val))
    table = fit_interval(y_val, pred_app)
    cov, width = interval_coverage(y_val, pred_app, table)
    return {"pipeline": pipe, "algorithm": algorithm, "label": ALGORITHMS[algorithm]["label"],
            "params": clean_params(algorithm, params), "log_target": bool(log_target),
            "augment_frac": float(augment_frac), "fit_seconds": round(seconds, 2),
            "train_size": int(len(train)), "val_full": compute_metrics(y_val, pred_full),
            "val_app": compute_metrics(y_val, pred_app), "interval": table,
            "val_interval_coverage_pct": cov, "val_interval_median_width_usd": width,
            "val_pred_app": pred_app, "val_true": y_val}


# --------------------------------------------------------------------------------------- lưu / registry
def read_registry():
    if REGISTRY_FILE.is_file():
        return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    return {"active": None, "models": []}


def write_registry(reg):
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_FILE.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")


def public_result(result):
    """Phần kết quả lưu được ra JSON (bỏ pipeline và mảng số)."""
    return {k: v for k, v in result.items() if k not in ("pipeline", "val_pred_app", "val_true")}


def save_version(result, note="", created_by="admin"):
    """Lưu pipeline vào registry (chưa đưa vào sử dụng). Trả về mã phiên bản."""
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    version = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + result["algorithm"]
    joblib.dump(result["pipeline"], REGISTRY_DIR / f"{version}.joblib", compress=3)
    reg = read_registry()
    entry = public_result(result)
    entry.update({"version": version, "file": f"registry/{version}.joblib", "note": note,
                  "created_by": created_by, "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
    reg["models"].append(entry)
    write_registry(reg)
    return version


def activate_version(version):
    """Đưa một phiên bản vào sử dụng: chép thành final_pipeline.joblib và cập nhật metrics.json
    (giá trị val, vì tập test chỉ được dùng một lần cho mô hình báo cáo)."""
    reg = read_registry()
    entry = next((m for m in reg["models"] if m["version"] == version), None)
    if entry is None:
        raise ValueError(f"Không tìm thấy phiên bản {version}")
    pipe = joblib.load(MODEL_DIR / entry["file"])
    joblib.dump(pipe, ACTIVE_PIPELINE, compress=3)
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8")) if METRICS_PATH.is_file() else {}
    metrics.update({"active_version": version, "model_name": entry["label"], "interval": entry["interval"],
                    "app_mae_usd": entry.get("test_app", entry["val_app"])["mae_usd"],
                    "app_mae_source": "test" if "test_app" in entry else "validation"})
    METRICS_PATH.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    reg["active"] = version
    write_registry(reg)
    try:                                   # bộ đệm của predict.load_pipeline phải nạp lại mô hình mới
        from src.prediction.predict import load_pipeline
        load_pipeline.cache_clear()
    except Exception:                      # noqa: BLE001
        pass
    return entry
