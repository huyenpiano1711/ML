"""
20_cross_validation.py - KIỂM TRA ĐỘ ỔN ĐỊNH BẰNG 5-FOLD CROSS-VALIDATION (sửa theo review ML-13)

So sánh trước đây chỉ dựa trên MỘT tập validation. Script này chạy 5-fold StratifiedGroupKFold
(theo nhóm xe, giữ phân phối giá) trên train + validation cho 3 mô hình chính, báo MAE trung bình ± độ lệch chuẩn
theo đường của ứng dụng. Tập test KHÔNG được dùng.

Đầu ra: reports/prediction/cross_validation.csv
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import json

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from src import config
from src.prediction import model_trainer as mt

MODELS = [("Ridge - log1p", "ridge", True, {"alpha": 10.0}),
          ("RandomForest - log1p", "rf", True, {"n_estimators": 60, "max_depth": 22, "min_samples_leaf": 4}),
          ("HGB - log1p (mô hình chọn)", "hgb", True, None)]


def main():
    train, val, _ = mt.load_splits()
    data = pd.concat([train, val], ignore_index=True)
    meta = json.loads(mt.METADATA_PATH.read_text(encoding="utf-8"))
    groups = data.groupby(["manufacturer", "model_base", "year", "odometer"], sort=False).ngroup()
    bins = pd.qcut(np.log1p(data["price"]), 10, labels=False)
    folds = list(StratifiedGroupKFold(5, shuffle=True, random_state=config.RANDOM_STATE).split(data, bins, groups))
    rows = []
    for name, algo, log_t, params in MODELS:
        params = params or meta["parameters"]
        maes = []
        for k, (tr, te) in enumerate(folds, 1):
            pipe, _ = mt.fit_model(data.iloc[tr], algo, params, log_t, meta.get("augment_frac", 0.5))
            part = data.iloc[te]
            maes.append(mt.compute_metrics(part["price"], mt.predict(pipe, mt.app_view(part)))["mae_usd"])
            print(f"{name:28s} fold {k}: MAE app ${maes[-1]:,.0f}", flush=True)
        rows.append({"mo_hinh": name, "mae_tb": round(np.mean(maes), 2), "mae_std": round(np.std(maes), 2),
                     **{f"fold_{i + 1}": m for i, m in enumerate(maes)}})
    out = pd.DataFrame(rows)
    out.to_csv(config.REPORT_DIR / "prediction" / "cross_validation.csv", index=False, encoding="utf-8-sig")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
