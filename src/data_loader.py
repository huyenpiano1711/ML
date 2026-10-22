"""
data_loader.py - Đọc dữ liệu gốc một cách tiết kiệm bộ nhớ.

File vehicles.csv nặng ~1.45 GB, phần lớn là cột 'description'. Ta chỉ đọc
các cột cần thiết (RAW_USECOLS) và ép kiểu hợp lý -> chỉ tốn ~450 MB RAM.
"""
import time

import pandas as pd

from src import config

# Ép kiểu khi đọc: id dùng int64, các cột số dùng float (vì có NaN).
RAW_DTYPES = {
    "id": "int64",
    "price": "int64",
    "year": "float64",
    "odometer": "float64",
    "county": "float64",
    "lat": "float64",
    "long": "float64",
}


def load_raw(usecols=None, nrows=None, verbose=True) -> pd.DataFrame:
    """Đọc vehicles.csv (bỏ qua description/image_url/region_url).

    Parameters
    ----------
    usecols : list | None   Danh sách cột cần đọc (mặc định config.RAW_USECOLS).
    nrows   : int | None    Đọc thử n dòng đầu để debug cho nhanh.
    """
    if not config.RAW_CSV.exists():
        raise FileNotFoundError(
            f"Không tìm thấy file dữ liệu: {config.RAW_CSV}\n"
            "-> Kiểm tra lại biến RAW_CSV trong src/config.py"
        )
    usecols = usecols or config.RAW_USECOLS
    dtypes = {c: t for c, t in RAW_DTYPES.items() if c in usecols}

    t0 = time.time()
    df = pd.read_csv(config.RAW_CSV, usecols=usecols, dtype=dtypes,
                     nrows=nrows, low_memory=False)
    if verbose:
        mb = df.memory_usage(deep=True).sum() / 1e6
        print(f"[load_raw] {len(df):,} dòng x {df.shape[1]} cột | "
              f"{mb:,.0f} MB RAM | {time.time() - t0:.1f}s")
    return df


def load_clean() -> pd.DataFrame:
    """Đọc dữ liệu đã làm sạch (ưu tiên file .pkl vì nhanh hơn)."""
    if config.CLEAN_PKL.exists():
        return pd.read_pickle(config.CLEAN_PKL)
    if config.CLEAN_CSV.exists():
        return pd.read_csv(config.CLEAN_CSV, low_memory=False)
    raise FileNotFoundError("Chưa có dữ liệu sạch -> hãy chạy 03_preprocess.py trước.")
