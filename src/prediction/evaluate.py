"""
evaluate.py - Vẽ 4 biểu đồ phân tích sai số của mô hình dự đoán giá trên tập test.

Được gọi từ scripts/19_train_final_model.py sau khi đánh giá mô hình cuối:
    generate_evaluation_plots(y_test, y_pred, test_df)
Đầu ra: reports/prediction/figures/01_actual_vs_predicted.png, 02_residuals_plot.png,
        03_error_by_price_segment.png, 04_error_by_manufacturer.png
Việc huấn luyện, đánh giá và lưu mô hình nằm ở src/prediction/model_trainer.py.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src import config

FIGURES_DIR = config.PROJECT_DIR / "reports" / "prediction" / "figures"


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
