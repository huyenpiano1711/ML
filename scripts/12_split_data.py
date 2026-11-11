"""
12_split_data.py - A03: CHIA DỮ LIỆU THÀNH TẬP TRAIN / VALIDATION / TEST (theo nhóm xe)

Tỷ lệ xấp xỉ 70% / 15% / 15%, random_state = 42 (config.RANDOM_STATE).
  - train      : cho mô hình học, fit các bước tiền xử lý (GroupModeImputer, encoder...)
  - validation : so sánh mô hình và chỉnh tham số
  - test       : chỉ dùng MỘT LẦN ở cuối để báo cáo kết quả

Hai nguyên tắc chống rò rỉ dữ liệu (sửa theo bản review 08/11):
  1. Chia THEO NHÓM XE: các tin có cùng hãng + dòng + năm + số dặm gần như chắc chắn là
     cùng một chiếc xe đăng lại, nên phải nằm chung một tập (StratifiedGroupKFold).
     Trước đây chia ngẫu nhiên từng tin -> 9% xe test có bản gần trùng trong train.
  2. Ngoại lai theo nhóm (giá lệch |robust z| > 3.5 so với xe cùng hãng + dòng + năm) được
     học ngưỡng CHỈ trên train và CHỈ loại khỏi train. Val/test giữ nguyên để đánh giá trung thực;
     các dòng val/test vượt ngưỡng chỉ được đánh dấu (eval_outlier_flags.csv) để phân tích thêm.

Chia theo "tầng" 10 khoảng log_price để phân phối giá ở 3 tập giống nhau.
Chỉ lưu CỘT id để file nhỏ và mọi thành viên dùng chung một cách chia.

Đầu vào : data/processed/vehicles_filled.pkl
Đầu ra  : data/splits/train_ids.csv, val_ids.csv, test_ids.csv
          reports/split_summary.csv, reports/removed_group_outliers.csv (chỉ train),
          reports/eval_outlier_flags.csv (val/test, chỉ đánh dấu)

Chạy: python 12_split_data.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # thư mục gốc repo
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import pandas as pd
import numpy as np
from sklearn.model_selection import StratifiedGroupKFold

from src import config
from src.cleaning import fit_group_outliers, flag_group_outliers

SPLIT_DIR = config.DATA_DIR / "splits"
SUMMARY_CSV = config.REPORT_DIR / "split_summary.csv"
N_FOLDS = 7            # 1/7 ≈ 14,3% làm test, 1/6 phần còn lại ≈ 14,3% làm val -> ~71/14/14
N_PRICE_BINS = 10
GROUP_KEY = ["manufacturer", "model_base", "year", "odometer"]


def vehicle_groups(df):
    """Mã nhóm xe: tin cùng hãng + dòng + năm + số dặm được coi là cùng một xe."""
    return df.groupby(GROUP_KEY, observed=True, sort=False).ngroup().to_numpy()


def take_one_fold(index, price_bin, groups, n_folds, seed):
    """Tách 1 fold (theo nhóm, giữ tỷ lệ khoảng giá) ra khỏi index -> (phần còn lại, fold)."""
    sgkf = StratifiedGroupKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    rest, fold = next(sgkf.split(index, price_bin, groups))
    return index[rest], index[fold]


def split_ids(df):
    """Trả về 3 mảng id: train, val, test (chưa loại ngoại lai)."""
    price_bin = pd.qcut(df["log_price"], q=N_PRICE_BINS, labels=False, duplicates="drop").to_numpy()
    groups = vehicle_groups(df)
    idx = np.arange(len(df))
    rest, test = take_one_fold(idx, price_bin, groups, N_FOLDS, config.RANDOM_STATE)
    tr, va = take_one_fold(np.arange(len(rest)), price_bin[rest], groups[rest], N_FOLDS - 1, config.RANDOM_STATE)
    ids = df["id"].to_numpy()
    return ids[rest[tr]], ids[rest[va]], ids[test]


def remove_train_outliers(df, parts):
    """Học ngưỡng ngoại lai trên train, loại khỏi train; val/test chỉ đánh dấu."""
    train = df[df["id"].isin(parts["train"])]
    stats = fit_group_outliers(train)
    z, out = flag_group_outliers(train, stats)
    removed = train.loc[out, ["id", "manufacturer", "model", "year", "odometer", "price", "seller_type"]] \
        .assign(price_robust_z=z[out]).sort_values("price_robust_z")
    removed.to_csv(config.REPORT_DIR / "removed_group_outliers.csv", index=False, encoding="utf-8-sig")
    print(f"Ngoại lai (ngưỡng học trên train): loại {len(removed):,} dòng khỏi train "
          f"({len(removed) / len(train) * 100:.2f}%)")
    flags = []
    for name in ("val", "test"):
        d = df[df["id"].isin(parts[name])]
        zz, oo = flag_group_outliers(d, stats)
        flags.append(pd.DataFrame({"id": d["id"], "tap": name, "price_robust_z": zz, "is_outlier": oo.astype(int)}))
        print(f"   {name}: {int(oo.sum()):,} dòng vượt ngưỡng (chỉ đánh dấu, KHÔNG loại)")
    pd.concat(flags).to_csv(config.REPORT_DIR / "eval_outlier_flags.csv", index=False, encoding="utf-8-sig")
    parts = dict(parts)
    parts["train"] = np.setdiff1d(parts["train"], removed["id"].to_numpy())
    return parts, set(removed["id"])


def cross_split_duplicates(df, parts):
    """Số xe test có bản trùng khóa nhóm trong train (kỳ vọng = 0 sau khi chia theo nhóm)."""
    key = df[GROUP_KEY].astype(str).agg("|".join, axis=1)
    tr = set(key[df["id"].isin(parts["train"])])
    return int(key[df["id"].isin(parts["test"])].isin(tr).sum())


def check_split(df, parts, removed=frozenset()):
    """Các kiểm tra bắt buộc: không trùng, không sót, không mất dòng (trừ ngoại lai train đã loại)."""
    sets = {k: set(v) for k, v in parts.items()}
    assert df["id"].is_unique, "id trong dữ liệu bị trùng"
    assert not (sets["train"] & sets["val"]), "train và val có id trùng nhau"
    assert not (sets["train"] & sets["test"]), "train và test có id trùng nhau"
    assert not (sets["val"] & sets["test"]), "val và test có id trùng nhau"
    assert set().union(*sets.values()) | set(removed) == set(df["id"]), "tổng 3 tập không bằng toàn bộ dữ liệu"
    print("Kiểm tra: không trùng id giữa các tập, không sót dòng nào -> OK")


def summarize(df, parts):
    """Bảng so sánh 3 tập: nếu chia tốt thì các con số gần như bằng nhau."""
    rows = []
    for name, ids in [("toan_bo", df["id"])] + list(parts.items()):
        d = df[df["id"].isin(ids)]
        rows.append({
            "tap": name,
            "so_dong": len(d),
            "pct": round(len(d) / len(df) * 100, 2),
            "gia_trung_binh": round(d["price"].mean()),
            "gia_trung_vi": round(d["price"].median()),
            "nam_trung_vi": d["year"].median(),
            "odometer_trung_vi": round(d["odometer"].median()),
            "pct_dai_ly": round((d["seller_type"] == "dealer").mean() * 100, 2),
            "so_hang": d["manufacturer"].nunique(),
            "so_dong_xe": d["make_model"].nunique(),
        })
    return pd.DataFrame(rows)


def main():
    df = pd.read_pickle(config.PROCESSED_DIR / "vehicles_filled.pkl")
    print(f"Đọc {len(df):,} dòng x {df.shape[1]} cột")

    train_ids, val_ids, test_ids = split_ids(df)
    parts = {"train": train_ids, "val": val_ids, "test": test_ids}
    parts, removed = remove_train_outliers(df, parts)
    check_split(df, parts, removed)
    print(f"Xe test có bản trùng (hãng+dòng+năm+số dặm) trong train: {cross_split_duplicates(df, parts):,}")

    SPLIT_DIR.mkdir(parents=True, exist_ok=True)
    for name, ids in parts.items():
        out = SPLIT_DIR / f"{name}_ids.csv"
        pd.DataFrame({"id": sorted(ids)}).to_csv(out, index=False)
        print(f"  {name:5s}: {len(ids):>7,} dòng ({len(ids) / len(df) * 100:.1f}%) -> {out.name}")

    # Dòng xe chỉ có ở val/test mà train không có: mô hình chưa từng thấy -> nên biết trước
    train_mm = set(df.loc[df["id"].isin(train_ids), "make_model"])
    for name in ("val", "test"):
        mm = df.loc[df["id"].isin(parts[name]), "make_model"]
        unseen = ~mm.isin(train_mm)
        print(f"  {name}: {int(unseen.sum()):,} xe ({unseen.mean() * 100:.2f}%) thuộc dòng xe train không có")

    summary = summarize(df, parts)
    summary.to_csv(SUMMARY_CSV, index=False, encoding="utf-8-sig")
    print(f"\n==> Đã lưu {SUMMARY_CSV}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
