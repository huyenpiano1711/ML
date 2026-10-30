"""
evaluate.py - TASK B04 & B05: Huấn luyện pipeline cuối cùng, lưu trữ và đánh giá trên tập test độc lập.

Quy trình:
  1. Nạp tập train + validation (168.736 dòng) để fit pipeline cuối cùng.
  2. Pipeline hợp nhất bao gồm:
     - FeatureEngineer: tạo các biến dẫn xuất (car_age, log_odometer, brand_tier, make_model...)
     - GroupModeImputer: điền unknown theo nhóm hãng+dòng+năm (fit trên train+val)
     - Preprocessor (ColumnTransformer): mã hóa OrdinalEncoder và passthrough số
     - Regressor: HistGradientBoostingRegressor với siêu tham số tối ưu từ B03
     - TransformedTargetRegressor: tự động log1p(price) khi fit và expm1 khi predict
  3. Lưu pipeline hoàn chỉnh vào models/price_prediction/final_pipeline.joblib.
  4. Đánh giá trên tập test độc lập (29.778 dòng, CHỈ dùng một lần):
     - MAE (USD)
     - RMSE (USD)
     - R² trên giá USD
     - MedAE (USD)
     - P90 Absolute Error (USD)
     - MAPE (%)
  5. Vẽ các biểu đồ báo cáo:
     - 01_actual_vs_predicted.png
     - 02_residuals_plot.png
     - 03_error_by_price_segment.png
     - 04_error_by_manufacturer.png
  6. Lưu kết quả vào models/price_prediction/metrics.json và cập nhật model_metadata.json.
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

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, median_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline

from src import config
from src.features.preprocessing import (
    ALL_PRICE_MODEL_FEATURES,
    FeatureEngineer,
    GroupModeImputer,
    build_hgb_preprocessor,
)

DATA_FILE = config.DATA_DIR / "processed" / "vehicles_filled.pkl"
SPLIT_DIR = config.DATA_DIR / "splits"
MODEL_DIR = config.PROJECT_DIR / "models" / "price_prediction"
REPORT_DIR = config.PROJECT_DIR / "reports" / "prediction"
FIGURES_DIR = REPORT_DIR / "figures"

PIPELINE_PATH = MODEL_DIR / "final_pipeline.joblib"
METADATA_PATH = MODEL_DIR / "model_metadata.json"
METRICS_PATH = MODEL_DIR / "metrics.json"

RAW_INPUT_COLS = [
    "manufacturer", "model_base", "year", "type", "odometer", "condition",
    "fuel", "transmission", "drive", "cylinders", "paint_color", "title_status", "state"
]
SPEC_COLS = ["drive", "cylinders", "type", "fuel", "transmission"]


def load_dataset_splits():
    """Tải và chuẩn bị các tập train, val, test với nguồn dữ liệu nguyên bản."""
    print("1. Đang tải vehicles_filled.pkl và các file split...", flush=True)
    df = pd.read_pickle(DATA_FILE)

    # Đặt lại các giá trị do group impute trước đó về 'unknown' để tránh data leakage
    for c in SPEC_COLS:
        df[c] = df[f"{c}_filled"].where(df[f"{c}_source"].isin(["listing", "vin"]), "unknown")

    train_ids = pd.read_csv(SPLIT_DIR / "train_ids.csv")["id"]
    val_ids = pd.read_csv(SPLIT_DIR / "val_ids.csv")["id"]
    test_ids = pd.read_csv(SPLIT_DIR / "test_ids.csv")["id"]

    train_df = df[df["id"].isin(train_ids)].copy()
    val_df = df[df["id"].isin(val_ids)].copy()
    test_df = df[df["id"].isin(test_ids)].copy()

    # Train + Val để huấn luyện final pipeline
    train_val_df = pd.concat([train_df, val_df], ignore_index=True)

    print(f"   Train: {len(train_df):,} | Val: {len(val_df):,} | Train+Val: {len(train_val_df):,} | Test: {len(test_df):,}", flush=True)
    return train_val_df, test_df, val_df


def build_final_pipeline(best_params=None):
    """Xây dựng Pipeline hoàn chỉnh khép kín từ dữ liệu thô đến giá USD dự đoán."""
    if best_params is None:
        best_params = {
            "learning_rate": 0.06,
            "max_iter": 600,
            "max_leaf_nodes": 80,
            "min_samples_leaf": 25,
            "l2_regularization": 0.5,
            "random_state": config.RANDOM_STATE
        }

    prep, cat_idx = build_hgb_preprocessor()

    base_pipe = Pipeline([
        ("feature_eng", FeatureEngineer()),
        ("group_imputer", GroupModeImputer(cols=SPEC_COLS)),
        ("prep", prep),
        ("reg", HistGradientBoostingRegressor(
            learning_rate=best_params["learning_rate"],
            max_iter=best_params["max_iter"],
            max_leaf_nodes=best_params["max_leaf_nodes"],
            min_samples_leaf=best_params["min_samples_leaf"],
            l2_regularization=best_params["l2_regularization"],
            categorical_features=cat_idx,
            random_state=best_params["random_state"]
        ))
    ])

    # Tự động hóa log1p(y) khi fit và expm1(pred) khi predict
    pipeline = TransformedTargetRegressor(
        regressor=base_pipe,
        func=np.log1p,
        inverse_func=np.expm1
    )
    return pipeline


def compute_metrics(y_true, y_pred):
    """Tính các chỉ số đánh giá theo yêu cầu."""
    y_true = np.asarray(y_true)
    y_pred = np.clip(np.asarray(y_pred), a_min=100.0, a_max=None)

    abs_errors = np.abs(y_true - y_pred)
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2_usd = float(r2_score(y_true, y_pred))
    medae = float(median_absolute_error(y_true, y_pred))
    p90 = float(np.percentile(abs_errors, 90))
    mape = float(np.mean(abs_errors / y_true) * 100)

    y_true_log = np.log1p(y_true)
    y_pred_log = np.log1p(y_pred)
    r2_log = float(r2_score(y_true_log, y_pred_log))

    return {
        "mae_usd": round(mae, 2),
        "rmse_usd": round(rmse, 2),
        "medae_usd": round(medae, 2),
        "p90_usd": round(p90, 2),
        "r2_usd": round(r2_usd, 4),
        "r2_log": round(r2_log, 4),
        "mape_pct": round(mape, 2),
        "sample_size": len(y_true)
    }


def generate_evaluation_plots(y_true, y_pred, test_df):
    """Tạo và lưu 4 biểu đồ phân tích sai số trên tập test."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    abs_errors = np.abs(np.asarray(y_true) - np.asarray(y_pred))
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    # 1. Actual vs Predicted
    print("   Vẽ biểu đồ 1: Actual vs Predicted...", flush=True)
    fig, ax = plt.subplots(figsize=(8, 7), dpi=150)
    # Lấy mẫu ngẫu nhiên 5000 điểm để hiển thị rõ mật độ
    np.random.seed(config.RANDOM_STATE)
    sample_idx = np.random.choice(len(y_true), size=min(5000, len(y_true)), replace=False)
    ax.scatter(y_true[sample_idx], y_pred[sample_idx], alpha=0.3, color="#2b5c8f", s=15, edgecolors="none")
    lims = [0, 100000]
    ax.plot(lims, lims, "r--", linewidth=1.5, label="Đường lý tưởng (y = x)")
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_xlabel("Giá thực tế (USD)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Giá dự đoán (USD)", fontsize=11, fontweight="bold")
    ax.set_title("So sánh Giá Thực tế vs Giá Dự đoán (Tập Test)", fontsize=12, fontweight="bold", pad=12)
    ax.legend(frameon=True)
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "01_actual_vs_predicted.png")
    plt.close(fig)

    # 2. Residual Plot
    print("   Vẽ biểu đồ 2: Residual Plot...", flush=True)
    residuals = y_true - y_pred
    fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
    ax.scatter(y_pred[sample_idx], residuals[sample_idx], alpha=0.3, color="#d95f02", s=15, edgecolors="none")
    ax.axhline(0, color="black", linestyle="--", linewidth=1.5)
    ax.set_xlim([0, 90000])
    ax.set_ylim([-30000, 30000])
    ax.set_xlabel("Giá dự đoán (USD)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Phần dư (Thực tế - Dự đoán, USD)", fontsize=11, fontweight="bold")
    ax.set_title("Phân tích Phần dư (Residual Plot - Tập Test)", fontsize=12, fontweight="bold", pad=12)
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "02_residuals_plot.png")
    plt.close(fig)

    # 3. Sai số theo phân khúc giá
    print("   Vẽ biểu đồ 3: Sai số theo phân khúc giá...", flush=True)
    price_bins = [0, 5000, 10000, 20000, 35000, 50000, 150000]
    bin_labels = ["< 5k", "5k - 10k", "10k - 20k", "20k - 35k", "35k - 50k", "> 50k"]
    test_analysis = test_df.copy()
    test_analysis["actual_price"] = y_true
    test_analysis["pred_price"] = y_pred
    test_analysis["abs_err"] = abs_errors
    test_analysis["price_segment"] = pd.cut(test_analysis["actual_price"], bins=price_bins, labels=bin_labels)

    segment_stats = test_analysis.groupby("price_segment", observed=True).agg(
        mae=("abs_err", "mean"),
        medae=("abs_err", "median"),
        count=("abs_err", "count")
    ).reset_index()

    fig, ax1 = plt.subplots(figsize=(9, 5), dpi=150)
    x = np.arange(len(segment_stats))
    width = 0.35
    ax1.bar(x - width/2, segment_stats["mae"], width, label="MAE (Trung bình)", color="#1b9e77")
    ax1.bar(x + width/2, segment_stats["medae"], width, label="MedAE (Trung vị)", color="#7570b3")
    ax1.set_xticks(x)
    ax1.set_xticklabels(segment_stats["price_segment"], fontsize=10)
    ax1.set_xlabel("Phân khúc giá thực tế (USD)", fontsize=11, fontweight="bold")
    ax1.set_ylabel("Sai số tuyệt đối (USD)", fontsize=11, fontweight="bold")
    ax1.set_title("Sai số Dự đoán theo Phân khúc Giá (Tập Test)", fontsize=12, fontweight="bold", pad=12)
    ax1.legend()

    for i in x:
        n = segment_stats.loc[i, "count"]
        ax1.text(i, max(segment_stats.loc[i, "mae"], segment_stats.loc[i, "medae"]) + 200, f"n={n:,}",
                 ha="center", fontsize=8, color="#555555")

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "03_error_by_price_segment.png")
    plt.close(fig)

    # 4. Sai số theo hãng xe hàng đầu
    print("   Vẽ biểu đồ 4: Sai số theo hãng xe...", flush=True)
    top_makes = test_analysis["manufacturer"].value_counts().head(12).index
    make_stats = test_analysis[test_analysis["manufacturer"].isin(top_makes)].groupby("manufacturer", observed=True).agg(
        mae=("abs_err", "mean"),
        medae=("abs_err", "median"),
        count=("abs_err", "count")
    ).sort_values("mae", ascending=True)

    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    y_pos = np.arange(len(make_stats))
    ax.barh(y_pos - 0.2, make_stats["mae"], height=0.4, label="MAE (USD)", color="#386cb0")
    ax.barh(y_pos + 0.2, make_stats["medae"], height=0.4, label="MedAE (USD)", color="#fdb462")
    ax.set_yticks(y_pos)
    ax.set_yticklabels([m.title() for m in make_stats.index], fontsize=10)
    ax.set_xlabel("Sai số tuyệt đối (USD)", fontsize=11, fontweight="bold")
    ax.set_title("Sai số Dự đoán ở 12 Hãng Xe Phổ Biến Nhất (Tập Test)", fontsize=12, fontweight="bold", pad=12)
    ax.legend(loc="lower right")
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "04_error_by_manufacturer.png")
    plt.close(fig)

    print("   => Đã lưu 4 biểu đồ vào reports/prediction/figures/")


def train_save_and_evaluate():
    """Hàm thực thi toàn bộ B04 và B05."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Đọc dữ liệu
    train_val_df, test_df, val_df = load_dataset_splits()

    # 2. Lấy tham số tối ưu từ B03
    best_params = {
        "learning_rate": 0.06,
        "max_iter": 600,
        "max_leaf_nodes": 80,
        "min_samples_leaf": 25,
        "l2_regularization": 0.5,
        "random_state": config.RANDOM_STATE
    }
    if METADATA_PATH.exists():
        try:
            with open(METADATA_PATH, "r", encoding="utf-8") as f:
                saved_meta = json.load(f)
                best_params.update(saved_meta.get("parameters", {}))
                print(f"   Đã nạp siêu tham số tối ưu từ metadata: {saved_meta.get('best_configuration')}")
        except Exception as e:
            print(f"   Cảnh báo nạp metadata: {e}, dùng tham số mặc định")

    # 3. Huấn luyện Pipeline cuối cùng trên Train + Val
    print("\n2. Huấn luyện Pipeline cuối cùng trên Train + Validation (168,736 xe)...", flush=True)
    t0 = time.time()
    final_pipeline = build_final_pipeline(best_params)
    X_train_val = train_val_df[RAW_INPUT_COLS]
    y_train_val = train_val_df["price"].to_numpy()

    final_pipeline.fit(X_train_val, y_train_val)
    train_time = time.time() - t0
    print(f"   Hoàn thành huấn luyện trong {train_time:.1f}s!", flush=True)

    # 4. Lưu Pipeline bằng Joblib
    print(f"\n3. Đang lưu mô hình vào {PIPELINE_PATH}...", flush=True)
    joblib.dump(final_pipeline, PIPELINE_PATH, compress=3)
    file_size_mb = os.path.getsize(PIPELINE_PATH) / (1024 * 1024)
    print(f"   Đã lưu thành công! Dung lượng file: {file_size_mb:.2f} MB", flush=True)

    # 5. Đánh giá trên tập test độc lập (B04)
    print("\n4. Đang đánh giá trên tập Test độc lập (29,778 xe)...", flush=True)
    X_test = test_df[RAW_INPUT_COLS]
    y_test = test_df["price"].to_numpy()

    t_pred0 = time.time()
    y_test_pred = final_pipeline.predict(X_test)
    pred_time = time.time() - t_pred0

    test_metrics = compute_metrics(y_test, y_test_pred)
    test_metrics["pred_time_sec"] = round(pred_time, 2)
    test_metrics["ms_per_car"] = round((pred_time / len(X_test)) * 1000, 3)

    print("\n=======================================================")
    print("KẾT QUẢ ĐÁNH GIÁ TRÊN TẬP TEST ĐỘC LẬP (TASK B04)")
    print("=======================================================")
    print(f"MAE (USD)             : ${test_metrics['mae_usd']:,.2f}")
    print(f"RMSE (USD)            : ${test_metrics['rmse_usd']:,.2f}")
    print(f"MedAE (USD)           : ${test_metrics['medae_usd']:,.2f}")
    print(f"P90 Absolute Error    : ${test_metrics['p90_usd']:,.2f}")
    print(f"R² trên giá USD       : {test_metrics['r2_usd']}")
    print(f"R² trên log_price     : {test_metrics['r2_log']}")
    print(f"MAPE                  : {test_metrics['mape_pct']}%")
    print(f"Thời gian dự đoán     : {test_metrics['pred_time_sec']}s ({test_metrics['ms_per_car']} ms/xe)")
    print("=======================================================")

    # 6. Vẽ biểu đồ phân tích
    print("\n5. Tạo các biểu đồ trực quan hóa sai số...", flush=True)
    generate_evaluation_plots(y_test, y_test_pred, test_df)

    # 7. Lưu metrics.json và cập nhật model_metadata.json
    metrics_data = {
        "model_name": "HistGradientBoostingRegressor",
        "pipeline_file": "final_pipeline.joblib",
        "test_metrics": test_metrics,
        "evaluation_notes": {
            "r2_calculation": "R² được tính trực tiếp trên giá USD thật theo công thức 1 - SS_res/SS_tot",
            "log_target_inverse": "Target huấn luyện là log1p(price), khi suy luận tự động chuyển ngược bằng expm1",
            "g1_outlier_impact": "Bước G1 loại bỏ 0.68% ngoại lai trước khi split nên kết quả test có thể lạc quan nhẹ nhưng phản ánh chính xác phân khúc xe phổ thông",
            "evaluated_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    }
    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics_data, f, indent=2, ensure_ascii=False)
    print(f"   Đã lưu {METRICS_PATH}")

    # Cập nhật metadata
    metadata = {
        "model_name": "HistGradientBoostingRegressor",
        "pipeline_class": "TransformedTargetRegressor(HistGradientBoostingRegressor)",
        "library": "scikit-learn",
        "pipeline_file": "final_pipeline.joblib",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "best_configuration": "HGB_iter600_lr06",
        "parameters": best_params,
        "target": {
            "name": "log_price",
            "formula": "log(1 + price)",
            "inverse": "np.expm1(prediction)",
            "unit": "USD"
        },
        "features": {
            "raw_input_columns": RAW_INPUT_COLS,
            "all_price_model_features": ALL_PRICE_MODEL_FEATURES,
            "group_impute_columns": SPEC_COLS
        },
        "training_data": {
            "dataset": "data/processed/vehicles_filled.pkl",
            "train_val_size": len(train_val_df),
            "test_size": len(test_df),
            "year_reference": config.SCRAPE_YEAR,
            "year_range": [1990, 2022],
            "price_range_usd": [1000, 150000],
            "random_seed": config.RANDOM_STATE
        },
        "performance": {
            "test_mae_usd": test_metrics["mae_usd"],
            "test_rmse_usd": test_metrics["rmse_usd"],
            "test_medae_usd": test_metrics["medae_usd"],
            "test_p90_usd": test_metrics["p90_usd"],
            "test_r2_usd": test_metrics["r2_usd"],
            "test_mape_pct": test_metrics["mape_pct"],
            "latency_ms_per_car": test_metrics["ms_per_car"]
        }
    }
    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"   Đã cập nhật {METADATA_PATH}")

    # 8. Kiểm tra load model trong tiến trình mới
    print("\n6. Kiểm tra tải lại pipeline từ file joblib...", flush=True)
    loaded_pipe = joblib.load(PIPELINE_PATH)
    sample_car = X_test.iloc[[0]]
    sample_actual = y_test[0]
    sample_pred = float(loaded_pipe.predict(sample_car)[0])
    print(f"   Xe mẫu: {sample_car['manufacturer'].values[0]} {sample_car['model_base'].values[0]} ({sample_car['year'].values[0]})")
    print(f"   Giá thực tế: ${sample_actual:,.2f} | Giá dự đoán: ${sample_pred:,.2f}")
    print("   ==> Model nạp lại thành công và dự đoán tức thì mà KHÔNG cần train lại!")

    return test_metrics


if __name__ == "__main__":
    train_save_and_evaluate()
