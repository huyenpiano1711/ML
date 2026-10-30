"""
tune.py - TASK B03: Tối ưu siêu tham số mô hình hồi quy tiềm năng (HistGradientBoosting).
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
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, median_absolute_error, mean_squared_error, r2_score

from src import config
from src.prediction.train import build_hgb_preprocessor, load_train_val_data

OUT_JSON = config.PROJECT_DIR / "models" / "price_prediction" / "model_metadata.json"
OUT_TRIALS_CSV = config.PROJECT_DIR / "reports" / "prediction" / "tuning_trials.csv"


def run_tuning():
    print("1. Tải dữ liệu train và val...", flush=True)
    train_df, val_df, imputer = load_train_val_data()

    schema = json.loads((config.PROJECT_DIR / "src" / "features" / "feature_schema.json").read_text(encoding="utf-8"))
    features = schema["price_model_columns"]["all"]

    X_tr = train_df[features]
    y_tr_log = train_df["log_price"].to_numpy()
    X_va = val_df[features]
    y_va_usd = val_df["price"].to_numpy()
    y_va_log = val_df["log_price"].to_numpy()

    # Preprocess
    print("2. Mã hóa dữ liệu bằng OrdinalEncoder...", flush=True)
    hgb_prep, cat_idx = build_hgb_preprocessor()
    X_tr_enc = hgb_prep.fit_transform(X_tr)
    X_va_enc = hgb_prep.transform(X_va)

    candidate_configs = [
        {"name": "HGB_base_300", "learning_rate": 0.1, "max_iter": 300, "max_leaf_nodes": 63, "min_samples_leaf": 20, "l2_regularization": 0.0},
        {"name": "HGB_iter400_lr08", "learning_rate": 0.08, "max_iter": 400, "max_leaf_nodes": 63, "min_samples_leaf": 20, "l2_regularization": 0.1},
        {"name": "HGB_iter500_lr08", "learning_rate": 0.08, "max_iter": 500, "max_leaf_nodes": 80, "min_samples_leaf": 20, "l2_regularization": 0.2},
        {"name": "HGB_iter600_lr06", "learning_rate": 0.06, "max_iter": 600, "max_leaf_nodes": 80, "min_samples_leaf": 25, "l2_regularization": 0.5},
        {"name": "HGB_iter500_lr05", "learning_rate": 0.05, "max_iter": 500, "max_leaf_nodes": 90, "min_samples_leaf": 20, "l2_regularization": 0.1},
        {"name": "HGB_leaf100_lr08", "learning_rate": 0.08, "max_iter": 400, "max_leaf_nodes": 100, "min_samples_leaf": 30, "l2_regularization": 1.0},
    ]

    trials = []
    print("\n3. Bắt đầu thử nghiệm các cấu hình siêu tham số trên Validation:")

    for cfg in candidate_configs:
        t0 = time.time()
        reg = HistGradientBoostingRegressor(
            learning_rate=cfg["learning_rate"],
            max_iter=cfg["max_iter"],
            max_leaf_nodes=cfg["max_leaf_nodes"],
            min_samples_leaf=cfg["min_samples_leaf"],
            l2_regularization=cfg["l2_regularization"],
            categorical_features=cat_idx,
            random_state=config.RANDOM_STATE
        )
        reg.fit(X_tr_enc, y_tr_log)
        fit_time = time.time() - t0

        pred_log = reg.predict(X_va_enc)
        pred_usd = np.expm1(pred_log)

        mae = float(mean_absolute_error(y_va_usd, pred_usd))
        rmse = float(np.sqrt(mean_squared_error(y_va_usd, pred_usd)))
        r2 = float(r2_score(y_va_usd, pred_usd))
        medae = float(median_absolute_error(y_va_usd, pred_usd))
        r2_log = float(r2_score(y_va_log, pred_log))
        mape = float(np.mean(np.abs(pred_usd - y_va_usd) / y_va_usd) * 100)

        trial = {
            "name": cfg["name"],
            "learning_rate": cfg["learning_rate"],
            "max_iter": cfg["max_iter"],
            "max_leaf_nodes": cfg["max_leaf_nodes"],
            "min_samples_leaf": cfg["min_samples_leaf"],
            "l2_regularization": cfg["l2_regularization"],
            "mae_usd": round(mae, 2),
            "rmse_usd": round(rmse, 2),
            "medae_usd": round(medae, 2),
            "r2_usd": round(r2, 4),
            "r2_log": round(r2_log, 4),
            "mape_pct": round(mape, 2),
            "fit_time_sec": round(fit_time, 2)
        }
        trials.append(trial)
        print(f"   [{cfg['name']}] MAE: ${mae:,.2f} | RMSE: ${rmse:,.2f} | R2(USD): {r2:.4f} | R2(log): {r2_log:.4f} | {fit_time:.1f}s", flush=True)

    trials_df = pd.DataFrame(trials)
    OUT_TRIALS_CSV.parent.mkdir(parents=True, exist_ok=True)
    trials_df.to_csv(OUT_TRIALS_CSV, index=False, encoding="utf-8-sig")
    print(f"\n==> Đã lưu lịch sử thử nghiệm vào {OUT_TRIALS_CSV}")

    # Chọn cấu hình tốt nhất dựa trên MAE và R2 trên validation
    best_idx = trials_df["mae_usd"].idxmin()
    best_trial = trials[best_idx]
    print(f"\n==> CẤU HÌNH TỐT NHẤT: {best_trial['name']}")
    print(f"    MAE: ${best_trial['mae_usd']:,.2f} | RMSE: ${best_trial['rmse_usd']:,.2f} | R2(USD): {best_trial['r2_usd']}")

    # Lưu metadata
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "model_name": "HistGradientBoostingRegressor",
        "library": "scikit-learn",
        "best_configuration": best_trial["name"],
        "parameters": {
            "learning_rate": best_trial["learning_rate"],
            "max_iter": best_trial["max_iter"],
            "max_leaf_nodes": best_trial["max_leaf_nodes"],
            "min_samples_leaf": best_trial["min_samples_leaf"],
            "l2_regularization": best_trial["l2_regularization"],
            "categorical_features": "native histogram binning (indices 0..10)",
            "random_state": config.RANDOM_STATE
        },
        "target": {
            "name": "log_price",
            "transform": "np.log1p",
            "inverse_transform": "np.expm1",
            "unit": "USD"
        },
        "features": {
            "all_features": features,
            "numeric_features": schema["price_model_columns"]["numeric"],
            "categorical_features": schema["price_model_columns"]["categorical"],
            "high_cardinality_features": schema["price_model_columns"]["high_cardinality"]
        },
        "data_version": {
            "dataset": "vehicles_filled.pkl (Craigslist 2021)",
            "scrape_year_reference": config.SCRAPE_YEAR,
            "train_size": len(train_df),
            "val_size": len(val_df),
            "split_random_state": config.RANDOM_STATE
        },
        "validation_metrics": {
            "mae_usd": best_trial["mae_usd"],
            "rmse_usd": best_trial["rmse_usd"],
            "medae_usd": best_trial["medae_usd"],
            "r2_usd": best_trial["r2_usd"],
            "r2_log": best_trial["r2_log"],
            "mape_pct": best_trial["mape_pct"]
        },
        "trials_history": trials
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"==> Đã lưu metadata vào {OUT_JSON}")

    return metadata


if __name__ == "__main__":
    run_tuning()
