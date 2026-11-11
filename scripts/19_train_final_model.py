"""
19_train_final_model.py - HUẤN LUYỆN LẠI MÔ HÌNH GIÁ SAU KHI SỬA RÒ RỈ DỮ LIỆU (thay cho train/tune/evaluate cũ)

Thứ tự chạy toàn bộ: 03_preprocess -> 08_fill_specs -> 12_split_data -> 19_train_final_model
                      -> python -m src.recommendation.build_catalog -> python -m src.recommendation.evaluate

Các bước:
  1. So sánh 6 cấu hình (Dummy, Ridge USD/log, RandomForest log, HGB USD/log) trên tập VALIDATION.
     Thước đo chọn mô hình: MAE (USD) theo đường của ứng dụng (3 ô tùy chọn để trống).
  2. Thử nghiệm bỏ/không bỏ bước che ngẫu nhiên 3 ô tùy chọn khi train (augment) cho mô hình tốt nhất.
  3. Tinh chỉnh tham số mô hình tốt nhất trên validation (lưới nhỏ).
  4. Huấn luyện mô hình cuối trên train, tính bảng khoảng giá từ validation.
  5. Đánh giá MỘT LẦN trên tập test: đủ thông tin, đường app, và bỏ các dòng test bị đánh dấu ngoại lai.
  6. Lưu final_pipeline.joblib, metrics.json, model_metadata.json, registry.json, bảng + biểu đồ báo cáo.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import joblib
import numpy as np
import pandas as pd

from src import config
from src.prediction import model_trainer as mt

REPORT_DIR = config.PROJECT_DIR / "reports" / "prediction"
CANDIDATES = [  # (tên, thuật toán, log_target, tham số)
    ("Dummy (median)", "dummy", False, {}),
    ("Ridge - USD", "ridge", False, {"alpha": 10.0}),
    ("Ridge - log1p", "ridge", True, {"alpha": 10.0}),
    ("RandomForest - log1p", "rf", True, {"n_estimators": 100, "max_depth": 22, "min_samples_leaf": 4}),
    ("HGB - USD", "hgb", False, {"learning_rate": 0.1, "max_iter": 300, "max_leaf_nodes": 63, "min_samples_leaf": 20,
                                 "l2_regularization": 0.0}),
    ("HGB - log1p", "hgb", True, {"learning_rate": 0.1, "max_iter": 300, "max_leaf_nodes": 63, "min_samples_leaf": 20,
                                  "l2_regularization": 0.0}),
]
HGB_GRID = [
    {"learning_rate": 0.1, "max_iter": 300, "max_leaf_nodes": 63, "min_samples_leaf": 20, "l2_regularization": 0.0},
    {"learning_rate": 0.08, "max_iter": 500, "max_leaf_nodes": 80, "min_samples_leaf": 20, "l2_regularization": 0.2},
    {"learning_rate": 0.06, "max_iter": 600, "max_leaf_nodes": 80, "min_samples_leaf": 25, "l2_regularization": 0.5},
    {"learning_rate": 0.05, "max_iter": 900, "max_leaf_nodes": 100, "min_samples_leaf": 25, "l2_regularization": 0.5},
    {"learning_rate": 0.08, "max_iter": 700, "max_leaf_nodes": 127, "min_samples_leaf": 40, "l2_regularization": 1.0},
    {"learning_rate": 0.04, "max_iter": 1200, "max_leaf_nodes": 127, "min_samples_leaf": 30, "l2_regularization": 1.0},
]


def row(name, res):
    return {"cau_hinh": name, "thuat_toan": res["label"], "log_target": res["log_target"],
            "augment_frac": res["augment_frac"], "tham_so": json.dumps(res["params"]),
            "val_mae_app": res["val_app"]["mae_usd"], "val_mae_day_du": res["val_full"]["mae_usd"],
            "val_rmse_app": res["val_app"]["rmse_usd"], "val_r2_app": res["val_app"]["r2_usd"],
            "val_mape_app": res["val_app"]["mape_pct"], "fit_giay": res["fit_seconds"]}


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    splits = mt.load_splits()
    train, val, test = splits
    print(f"Train {len(train):,} | Val {len(val):,} | Test {len(test):,}")

    # 1. So sánh mô hình -----------------------------------------------------------------------------
    rows = []
    for name, algo, log_t, params in CANDIDATES:
        res = mt.train_and_validate(algo, params, log_t, 0.5, splits)
        rows.append(row(name, res))
        print(f"[1] {name:22s} MAE app ${res['val_app']['mae_usd']:>9,.0f} | đủ TT ${res['val_full']['mae_usd']:>9,.0f}"
              f" | {res['fit_seconds']:.0f}s", flush=True)
    comp = pd.DataFrame(rows)
    comp.to_csv(REPORT_DIR / "model_comparison.csv", index=False, encoding="utf-8-sig")
    best = comp.loc[comp["val_mae_app"].idxmin()]
    best_algo = next(c for c in CANDIDATES if c[0] == best["cau_hinh"])
    print(f"==> Tốt nhất trên validation: {best['cau_hinh']}")

    # 2. Có che ngẫu nhiên 3 ô khi train hay không -----------------------------------------------------
    aug_rows = []
    for frac in (0.0, 0.25, 0.5, 0.75):
        res = mt.train_and_validate(best_algo[1], best_algo[3], best_algo[2], frac, splits)
        aug_rows.append(row(f"augment {frac}", res))
        print(f"[2] augment={frac:.2f} MAE app ${res['val_app']['mae_usd']:,.0f} | đủ TT ${res['val_full']['mae_usd']:,.0f}",
              flush=True)
    aug = pd.DataFrame(aug_rows)
    aug.to_csv(REPORT_DIR / "augment_experiment.csv", index=False, encoding="utf-8-sig")
    # chọn tỷ lệ che làm MAE trung bình 2 đường thấp nhất
    aug["avg"] = (aug["val_mae_app"] + aug["val_mae_day_du"]) / 2
    best_frac = float(aug.loc[aug["avg"].idxmin(), "augment_frac"])
    print(f"==> Tỷ lệ che chọn: {best_frac}")

    # 3. Tinh chỉnh (chỉ cho HGB - mô hình được chọn) -------------------------------------------------
    trials = []
    best_params, best_mae, best_res = best_algo[3], float("inf"), None
    grid = HGB_GRID if best_algo[1] == "hgb" else [best_algo[3]]
    for i, params in enumerate(grid, 1):
        res = mt.train_and_validate(best_algo[1], params, best_algo[2], best_frac, splits)
        trials.append(row(f"trial_{i}", res))
        print(f"[3] trial {i}: {params} -> MAE app ${res['val_app']['mae_usd']:,.0f}", flush=True)
        if res["val_app"]["mae_usd"] < best_mae:
            best_params, best_mae, best_res = params, res["val_app"]["mae_usd"], res
    pd.DataFrame(trials).to_csv(REPORT_DIR / "tuning_trials.csv", index=False, encoding="utf-8-sig")

    # 4-5. Mô hình cuối + test một lần -----------------------------------------------------------------
    final = best_res
    pipe = final["pipeline"]
    y_test = test["price"].to_numpy(dtype=float)
    pred_full = mt.predict(pipe, test)
    pred_app = mt.predict(pipe, mt.app_view(test))
    flags = pd.read_csv(config.REPORT_DIR / "eval_outlier_flags.csv")
    flagged = set(flags.loc[(flags["tap"] == "test") & (flags["is_outlier"] == 1), "id"])
    clean = ~test["id"].isin(flagged).to_numpy()
    cov, width = mt.interval_coverage(y_test, pred_app, final["interval"])
    test_metrics = {"full_info": mt.compute_metrics(y_test, pred_full),
                    "app_path": mt.compute_metrics(y_test, pred_app),
                    "app_path_without_flagged_outliers": mt.compute_metrics(y_test[clean], pred_app[clean]),
                    "interval_coverage_pct": cov, "interval_median_width_usd": width,
                    "n_flagged_outliers": int((~clean).sum())}
    print(json.dumps(test_metrics, indent=2, ensure_ascii=False))

    final["test_full"], final["test_app"] = test_metrics["full_info"], test_metrics["app_path"]
    version = mt.save_version(final, note="Mô hình báo cáo (scripts/19)", created_by="script")
    mt.activate_version(version)

    metrics = {
        "model_name": final["label"], "active_version": version,
        "selection_metric": "MAE (USD) trên validation theo đường của ứng dụng",
        "test_metrics": test_metrics["full_info"],           # giữ khóa cũ cho code/ báo cáo cũ
        "test_metrics_app_path": test_metrics["app_path"],
        "test_metrics_app_path_without_flagged_outliers": test_metrics["app_path_without_flagged_outliers"],
        "validation_metrics_app_path": final["val_app"], "validation_metrics_full_info": final["val_full"],
        "interval": final["interval"], "interval_test_coverage_pct": cov,
        "interval_test_median_width_usd": width, "app_mae_usd": test_metrics["app_path"]["mae_usd"],
        "app_mae_source": "test",
        "evaluation_notes": {
            "split": "StratifiedGroupKFold theo nhóm hãng+dòng+năm+số dặm (tin đăng lại nằm chung một tập)",
            "outliers": "Ngưỡng ngoại lai học trên train, chỉ loại khỏi train; val/test giữ nguyên",
            "app_path": "drive, cylinders, paint_color = unknown như khi người dùng để trống",
            "interval": f"Khoảng {int(mt.INTERVAL_COVERAGE * 100)}% từ phân vị tỷ lệ giá thật/giá dự đoán trên validation, 5 mức giá",
            "test_used_once": True, "evaluated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
    mt.METRICS_PATH.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    meta = {"model_name": final["label"], "version": version, "library": "scikit-learn",
            "pipeline_file": "final_pipeline.joblib", "created_at": metrics["evaluation_notes"]["evaluated_at"],
            "parameters": final["params"], "log_target": final["log_target"], "augment_frac": final["augment_frac"],
            "raw_input_columns": mt.RAW_INPUT_COLS, "train_size": len(train), "val_size": len(val),
            "test_size": len(test), "random_seed": config.RANDOM_STATE}
    mt.METADATA_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # 6. Bảng + biểu đồ cho báo cáo ------------------------------------------------------------------
    t = test.assign(pred=pred_app, abs_err=np.abs(y_test - pred_app))
    t["muc_gia"] = pd.cut(t["price"], [0, 5000, 10000, 20000, 35000, 60000, 150001],
                          labels=["<5k", "5-10k", "10-20k", "20-35k", "35-60k", ">60k"])
    seg = t.groupby("muc_gia", observed=True).agg(so_xe=("price", "size"), mae=("abs_err", "mean"),
                                                   mape=("abs_err", lambda s: 0)).reset_index()
    seg["mape"] = t.groupby("muc_gia", observed=True).apply(lambda d: (d["abs_err"] / d["price"]).mean() * 100,
                                                            include_groups=False).to_numpy()
    seg.round(2).to_csv(REPORT_DIR / "error_by_price_segment.csv", index=False, encoding="utf-8-sig")
    top = t.groupby("manufacturer").agg(so_xe=("price", "size"), mae=("abs_err", "mean")).query("so_xe >= 200") \
        .sort_values("mae", ascending=False).round(2)
    top.to_csv(REPORT_DIR / "error_by_manufacturer.csv", encoding="utf-8-sig")
    try:
        from src.prediction.evaluate import generate_evaluation_plots
        generate_evaluation_plots(y_test, pred_app, t)
    except Exception as exc:                                 # noqa: BLE001
        print(f"   (không vẽ được biểu đồ: {exc})")
    print(f"\n==> Đã lưu mô hình {version} và đưa vào sử dụng")


if __name__ == "__main__":
    main()
