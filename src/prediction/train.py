"""
train.py - TASK B02: Huấn luyện và so sánh các mô hình hồi quy dự đoán giá xe.

Mô hình huấn luyện:
  1. DummyRegressor (Baseline - đoán trung vị)
  2. Ridge Regression (Direct USD target)
  3. Ridge Regression (Log-price target -> expm1)
  4. RandomForestRegressor (Log-price target -> expm1)
  5. HistGradientBoostingRegressor (Direct USD target)
  6. HistGradientBoostingRegressor (Log-price target -> expm1)

Nguyên tắc:
  - Sử dụng đúng tập train/val từ data/splits/*.csv.
  - Các mô hình so sánh trên cùng bộ 17 đặc trưng (feature_schema.json).
  - Preprocessing bằng Pipeline / ColumnTransformer.
  - GroupModeImputer và mọi encoder/scaler chỉ fit trên tập train (tránh data leakage).
  - Categorical features trong HistGradientBoosting được xử lý theo chuẩn categorical histogram splits.
  - Đánh giá MAE, RMSE, R² trên đơn vị giá USD thật (không nhầm lẫn với R² log).
  - Ghi nhận thời gian huấn luyện và xuất bảng so sánh ra reports/prediction/model_comparison.csv.
"""
import json
import os
import sys
import time
from pathlib import Path

# Đảm bảo UTF-8 và tìm thấy thư mục gốc
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, median_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

from src import config
from src.features.preprocessing import (
    ALL_PRICE_MODEL_FEATURES,
    CONDITION_ORDER,
    PRICE_MODEL_CATEGORICAL,
    PRICE_MODEL_HIGH_CARD,
    PRICE_MODEL_NUMERIC,
    FeatureEngineer,
    GroupModeImputer,
    add_features,
)

DATA_FILE = config.DATA_DIR / "processed" / "vehicles_filled.pkl"
SPLIT_DIR = config.DATA_DIR / "splits"
REPORT_DIR = config.PROJECT_DIR / "reports" / "prediction"
SCHEMA_FILE = config.PROJECT_DIR / "src" / "features" / "feature_schema.json"
OUT_CSV = REPORT_DIR / "model_comparison.csv"

SPEC_COLS = ["drive", "cylinders", "type", "fuel", "transmission"]


def load_train_val_data():
    """Tải dữ liệu và chuẩn bị tập train, val không bị rò rỉ dữ liệu."""
    print("1. Đang tải dữ liệu và phân chia tập...", flush=True)
    df = pd.read_pickle(DATA_FILE)

    # Đặt lại các giá trị được điền bằng group về 'unknown' để tránh rò rỉ
    for c in SPEC_COLS:
        df[c] = df[f"{c}_filled"].where(df[f"{c}_source"].isin(["listing", "vin"]), "unknown")

    train_ids = pd.read_csv(SPLIT_DIR / "train_ids.csv")["id"]
    val_ids = pd.read_csv(SPLIT_DIR / "val_ids.csv")["id"]

    train_df = df[df["id"].isin(train_ids)].copy()
    val_df = df[df["id"].isin(val_ids)].copy()

    # Tính đặc trưng và fit GroupModeImputer CHỈ trên tập train
    print(f"   Train: {len(train_df):,} dòng | Validation: {len(val_df):,} dòng", flush=True)
    imputer = GroupModeImputer(cols=SPEC_COLS)

    train_df = add_features(train_df)
    imputer.fit(train_df)
    train_df = imputer.transform(train_df)

    val_df = add_features(val_df)
    val_df = imputer.transform(val_df)

    return train_df, val_df, imputer


def build_linear_preprocessor():
    """Tạo ColumnTransformer cho Ridge: scale số, one-hot phân loại (sparse matrix)."""
    from sklearn.impute import SimpleImputer
    num_pipe = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler())
    ])
    cat_pipe = OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=25, sparse_output=True)
    high_pipe = OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=30, sparse_output=True)

    return ColumnTransformer([
        ("num", num_pipe, PRICE_MODEL_NUMERIC),
        ("cat", cat_pipe, PRICE_MODEL_CATEGORICAL),
        ("high", high_pipe, PRICE_MODEL_HIGH_CARD)
    ])


def build_hgb_preprocessor():
    """Tạo ColumnTransformer cho HistGradientBoosting: OrdinalEncoder cho categorical, passthrough số."""
    all_cat = PRICE_MODEL_CATEGORICAL + PRICE_MODEL_HIGH_CARD
    enc = OrdinalEncoder(
        handle_unknown="use_encoded_value",
        unknown_value=-1,
        encoded_missing_value=-1,
        max_categories=250
    )
    # Cột categorical ở trước [0 .. len(all_cat)-1], cột số ở sau
    prep = ColumnTransformer([
        ("cat", enc, all_cat),
        ("num", "passthrough", PRICE_MODEL_NUMERIC)
    ])
    cat_indices = list(range(len(all_cat)))
    return prep, cat_indices


def evaluate_predictions(y_true_usd, pred_usd, pred_log=None):
    """Tính các độ đo chuẩn: MAE, RMSE, R² trên giá USD."""
    # Đảm bảo dự đoán không âm
    pred_usd = np.clip(pred_usd, a_min=100.0, a_max=None)
    y_true_usd = np.asarray(y_true_usd)

    mae = float(mean_absolute_error(y_true_usd, pred_usd))
    medae = float(median_absolute_error(y_true_usd, pred_usd))
    rmse = float(np.sqrt(mean_squared_error(y_true_usd, pred_usd)))
    r2_usd = float(r2_score(y_true_usd, pred_usd))

    y_true_log = np.log1p(y_true_usd)
    if pred_log is None:
        pred_log = np.log1p(pred_usd)
    r2_log = float(r2_score(y_true_log, pred_log))
    mape = float(np.mean(np.abs(pred_usd - y_true_usd) / y_true_usd) * 100)

    return {
        "mae_usd": round(mae, 2),
        "rmse_usd": round(rmse, 2),
        "medae_usd": round(medae, 2),
        "r2_usd": round(r2_usd, 4),
        "r2_log": round(r2_log, 4),
        "mape_pct": round(mape, 2)
    }


def train_and_evaluate_all():
    """Huấn luyện tất cả mô hình và ghi kết quả so sánh."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    train_df, val_df, _ = load_train_val_data()

    features = ALL_PRICE_MODEL_FEATURES
    X_train = train_df[features]
    y_train_usd = train_df["price"].to_numpy()
    y_train_log = train_df["log_price"].to_numpy()

    X_val = val_df[features]
    y_val_usd = val_df["price"].to_numpy()
    y_val_log = val_df["log_price"].to_numpy()

    results = []

    # 1. Baseline: DummyRegressor (luôn đoán trung vị train)
    print("\n--- Model 1: DummyRegressor (Baseline) ---", flush=True)
    t0 = time.time()
    dummy = DummyRegressor(strategy="median")
    dummy.fit(X_train[["car_age"]], y_train_usd)
    pred_val_dummy = dummy.predict(X_val[["car_age"]])
    t_fit = time.time() - t0

    metrics = evaluate_predictions(y_val_usd, pred_val_dummy)
    results.append({
        "model": "DummyRegressor",
        "target": "Direct USD",
        "configuration": "strategy='median'",
        "mae_usd": metrics["mae_usd"],
        "rmse_usd": metrics["rmse_usd"],
        "medae_usd": metrics["medae_usd"],
        "r2_usd": metrics["r2_usd"],
        "r2_log": metrics["r2_log"],
        "mape_pct": metrics["mape_pct"],
        "fit_time_sec": round(t_fit, 2)
    })
    print(f"   MAE: ${metrics['mae_usd']:,.2f} | RMSE: ${metrics['rmse_usd']:,.2f} | R2(USD): {metrics['r2_usd']} | {t_fit:.2f}s", flush=True)

    # 2. Ridge Regression - Direct Target
    print("\n--- Model 2: Ridge Regression (Direct USD Target) ---", flush=True)
    t0 = time.time()
    linear_prep = build_linear_preprocessor()
    ridge_direct = Pipeline([
        ("prep", linear_prep),
        ("reg", Ridge(alpha=10.0, random_state=config.RANDOM_STATE))
    ])
    ridge_direct.fit(X_train, y_train_usd)
    pred_val_ridge_dir = ridge_direct.predict(X_val)
    t_fit = time.time() - t0

    metrics = evaluate_predictions(y_val_usd, pred_val_ridge_dir)
    results.append({
        "model": "Ridge Regression",
        "target": "Direct USD",
        "configuration": "alpha=10.0, OneHotEncoder",
        "mae_usd": metrics["mae_usd"],
        "rmse_usd": metrics["rmse_usd"],
        "medae_usd": metrics["medae_usd"],
        "r2_usd": metrics["r2_usd"],
        "r2_log": metrics["r2_log"],
        "mape_pct": metrics["mape_pct"],
        "fit_time_sec": round(t_fit, 2)
    })
    print(f"   MAE: ${metrics['mae_usd']:,.2f} | RMSE: ${metrics['rmse_usd']:,.2f} | R2(USD): {metrics['r2_usd']} | {t_fit:.2f}s", flush=True)

    # 3. Ridge Regression - Log Target (log1p -> expm1)
    print("\n--- Model 3: Ridge Regression (Log-Price Target) ---", flush=True)
    t0 = time.time()
    ridge_log = Pipeline([
        ("prep", build_linear_preprocessor()),
        ("reg", Ridge(alpha=10.0, random_state=config.RANDOM_STATE))
    ])
    ridge_log.fit(X_train, y_train_log)
    pred_val_ridge_log = ridge_log.predict(X_val)
    pred_val_ridge_usd = np.expm1(pred_val_ridge_log)
    t_fit = time.time() - t0

    metrics = evaluate_predictions(y_val_usd, pred_val_ridge_usd, pred_val_ridge_log)
    results.append({
        "model": "Ridge Regression",
        "target": "Log-Price (log1p)",
        "configuration": "alpha=10.0, OneHotEncoder, expm1 inverse",
        "mae_usd": metrics["mae_usd"],
        "rmse_usd": metrics["rmse_usd"],
        "medae_usd": metrics["medae_usd"],
        "r2_usd": metrics["r2_usd"],
        "r2_log": metrics["r2_log"],
        "mape_pct": metrics["mape_pct"],
        "fit_time_sec": round(t_fit, 2)
    })
    print(f"   MAE: ${metrics['mae_usd']:,.2f} | RMSE: ${metrics['rmse_usd']:,.2f} | R2(USD): {metrics['r2_usd']} | {t_fit:.2f}s", flush=True)

    # 4. HistGradientBoostingRegressor - Direct USD Target
    print("\n--- Model 4: HistGradientBoosting (Direct USD Target) ---", flush=True)
    t0 = time.time()
    hgb_prep_dir, cat_idx = build_hgb_preprocessor()
    hgb_direct = Pipeline([
        ("prep", hgb_prep_dir),
        ("reg", HistGradientBoostingRegressor(
            max_iter=300,
            learning_rate=0.1,
            max_leaf_nodes=63,
            categorical_features=cat_idx,
            random_state=config.RANDOM_STATE
        ))
    ])
    hgb_direct.fit(X_train, y_train_usd)
    pred_val_hgb_dir = hgb_direct.predict(X_val)
    t_fit = time.time() - t0

    metrics = evaluate_predictions(y_val_usd, pred_val_hgb_dir)
    results.append({
        "model": "HistGradientBoosting",
        "target": "Direct USD",
        "configuration": "max_iter=300, lr=0.1, max_leaf_nodes=63, native categorical",
        "mae_usd": metrics["mae_usd"],
        "rmse_usd": metrics["rmse_usd"],
        "medae_usd": metrics["medae_usd"],
        "r2_usd": metrics["r2_usd"],
        "r2_log": metrics["r2_log"],
        "mape_pct": metrics["mape_pct"],
        "fit_time_sec": round(t_fit, 2)
    })
    print(f"   MAE: ${metrics['mae_usd']:,.2f} | RMSE: ${metrics['rmse_usd']:,.2f} | R2(USD): {metrics['r2_usd']} | {t_fit:.2f}s", flush=True)

    # 5. HistGradientBoostingRegressor - Log-Price Target
    print("\n--- Model 5: HistGradientBoosting (Log-Price Target) ---", flush=True)
    t0 = time.time()
    hgb_prep_log, cat_idx = build_hgb_preprocessor()
    hgb_log = Pipeline([
        ("prep", hgb_prep_log),
        ("reg", HistGradientBoostingRegressor(
            max_iter=300,
            learning_rate=0.1,
            max_leaf_nodes=63,
            categorical_features=cat_idx,
            random_state=config.RANDOM_STATE
        ))
    ])
    hgb_log.fit(X_train, y_train_log)
    pred_val_hgb_log = hgb_log.predict(X_val)
    pred_val_hgb_usd = np.expm1(pred_val_hgb_log)
    t_fit = time.time() - t0

    metrics = evaluate_predictions(y_val_usd, pred_val_hgb_usd, pred_val_hgb_log)
    results.append({
        "model": "HistGradientBoosting",
        "target": "Log-Price (log1p)",
        "configuration": "max_iter=300, lr=0.1, max_leaf_nodes=63, expm1 inverse",
        "mae_usd": metrics["mae_usd"],
        "rmse_usd": metrics["rmse_usd"],
        "medae_usd": metrics["medae_usd"],
        "r2_usd": metrics["r2_usd"],
        "r2_log": metrics["r2_log"],
        "mape_pct": metrics["mape_pct"],
        "fit_time_sec": round(t_fit, 2)
    })
    print(f"   MAE: ${metrics['mae_usd']:,.2f} | RMSE: ${metrics['rmse_usd']:,.2f} | R2(USD): {metrics['r2_usd']} | {t_fit:.2f}s", flush=True)

    # 6. RandomForestRegressor - Log-Price Target
    print("\n--- Model 6: RandomForestRegressor (Log-Price Target) ---", flush=True)
    t0 = time.time()
    rf_prep, _ = build_hgb_preprocessor()
    rf_model = Pipeline([
        ("prep", rf_prep),
        ("reg", RandomForestRegressor(
            n_estimators=100,
            max_depth=22,
            min_samples_leaf=4,
            n_jobs=-1,
            random_state=config.RANDOM_STATE
        ))
    ])
    rf_model.fit(X_train, y_train_log)
    pred_val_rf_log = rf_model.predict(X_val)
    pred_val_rf_usd = np.expm1(pred_val_rf_log)
    t_fit = time.time() - t0

    metrics = evaluate_predictions(y_val_usd, pred_val_rf_usd, pred_val_rf_log)
    results.append({
        "model": "RandomForestRegressor",
        "target": "Log-Price (log1p)",
        "configuration": "n_estimators=100, max_depth=22, min_samples_leaf=4, expm1 inverse",
        "mae_usd": metrics["mae_usd"],
        "rmse_usd": metrics["rmse_usd"],
        "medae_usd": metrics["medae_usd"],
        "r2_usd": metrics["r2_usd"],
        "r2_log": metrics["r2_log"],
        "mape_pct": metrics["mape_pct"],
        "fit_time_sec": round(t_fit, 2)
    })
    print(f"   MAE: ${metrics['mae_usd']:,.2f} | RMSE: ${metrics['rmse_usd']:,.2f} | R2(USD): {metrics['r2_usd']} | {t_fit:.2f}s", flush=True)

    # Xuất báo cáo so sánh
    res_df = pd.DataFrame(results)
    res_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n=======================================================")
    print(f"BẢNG SO SÁNH CÁC MÔ HÌNH HỒI QUY (TẬP VALIDATION: {len(val_df):,} DÒNG)")
    print(f"=======================================================")
    print(res_df.to_string(index=False))
    print(f"\n==> Đã lưu kết quả so sánh vào {OUT_CSV}")

    return res_df


if __name__ == "__main__":
    train_and_evaluate_all()
