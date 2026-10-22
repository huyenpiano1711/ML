"""
features.py - Tạo đặc trưng mới (feature engineering) và dựng Pipeline tiền xử lý
cho giai đoạn train mô hình.

Lưu ý quan trọng về RÒ RỈ DỮ LIỆU (data leakage):
  - Các đặc trưng ở hàm add_features() chỉ dùng thông tin của CHÍNH DÒNG ĐÓ
    (tuổi xe, dặm/năm...) -> an toàn khi tạo trước khi chia train/test.
  - Các bước học từ dữ liệu (impute trung vị, scale, one-hot, gom nhóm hiếm)
    nằm trong build_preprocessor() và CHỈ được fit trên tập train.
"""
import numpy as np
import pandas as pd

from src import config

LUXURY = {"bmw", "mercedes-benz", "audi", "lexus", "cadillac", "acura", "infiniti", "lincoln",
          "volvo", "land rover", "jaguar", "porsche", "tesla", "alfa-romeo", "genesis", "maserati"}
EXOTIC = {"ferrari", "aston-martin", "lamborghini", "mclaren", "bentley", "rolls-royce", "morgan", "lotus"}

CONDITION_ORDER = {"salvage": 0, "fair": 1, "good": 2, "excellent": 3, "like new": 4, "new": 5}


def add_features(df):
    df = df.copy()
    df["car_age"] = (config.SCRAPE_YEAR - df["year"]).clip(lower=0)
    # dặm/năm: xe mới (tuổi 0) tính là 1 năm để tránh chia cho 0
    df["miles_per_year"] = df["odometer"] / df["car_age"].clip(lower=1)
    df["log_price"] = np.log1p(df["price"])           # biến mục tiêu đề xuất (giảm lệch phải)
    df["log_odometer"] = np.log1p(df["odometer"])
    df["cylinders_num"] = pd.to_numeric(df["cylinders"].str.extract(r"(\d+)")[0], errors="coerce")
    df["condition_rank"] = df["condition"].map(CONDITION_ORDER)   # NaN khi 'unknown'
    df["brand_tier"] = np.select(
        [df["manufacturer"].isin(EXOTIC), df["manufacturer"].isin(LUXURY)],
        ["exotic", "luxury"], default="mainstream")
    df["has_vin"] = df["VIN"].notna().astype("int8")
    df["make_model"] = df["manufacturer"] + " " + df["model_base"]
    df["posting_dow"] = df["posting_date"].dt.dayofweek          # 0 = thứ Hai
    # Số thông số người bán bỏ trống -> mức độ "chăm chút" của tin đăng
    info_cols = ["condition", "cylinders", "drive", "type", "paint_color"]
    df["n_unknown_specs"] = (df[info_cols] == "unknown").sum(axis=1).astype("int8")
    return df


# ---------------------------------------------------------------------------
# Điền 'unknown' bằng giá trị phổ biến nhất của nhóm xe giống nhau (bài toán Completion)
# ---------------------------------------------------------------------------
class GroupModeImputer:
    """Điền 'unknown' bằng giá trị phổ biến nhất trong nhóm hãng+dòng+năm, nếu không đủ thì
    nhóm hãng+dòng. Chỉ điền khi nhóm có >= min_n xe đã biết giá trị và >= min_purity xe
    cùng một giá trị (vd 90% Ford F-150 2015 là 4wd thì mới điền 4wd).

    Dùng như một bước của sklearn: fit() CHỈ trên tập train, transform() cho cả train và test
    -> không rò rỉ thông tin của tập test.
    """

    def __init__(self, cols, levels=(("make_model", "year"), ("make_model",)),
                 min_n=10, min_purity=0.9, missing="unknown"):
        self.cols, self.levels = list(cols), [list(lv) for lv in levels]
        self.min_n, self.min_purity, self.missing = min_n, min_purity, missing

    def fit(self, X, y=None):
        self.tables_ = {}
        for col in self.cols:
            known = X[X[col] != self.missing]
            self.tables_[col] = []
            for keys in self.levels:
                cnt = known.groupby(keys + [col], observed=True).size().rename("n").reset_index()
                tot = cnt.groupby(keys, observed=True)["n"].transform("sum")
                cnt["purity"] = cnt["n"] / tot
                cnt["total"] = tot
                best = cnt.sort_values("n", ascending=False).drop_duplicates(keys)
                best = best[(best["total"] >= self.min_n) & (best["purity"] >= self.min_purity)]
                self.tables_[col].append(best[keys + [col]].rename(columns={col: "_fill"}))
        return self

    def transform(self, X, return_source=False):
        X = X.copy()
        sources = {}
        for col in self.cols:
            src = pd.Series(np.where(X[col] != self.missing, "known", self.missing), index=X.index, dtype="object")
            for keys, table in zip(self.levels, self.tables_[col]):
                need = X[col] == self.missing
                if not need.any():
                    break
                looked = X.loc[need, keys].merge(table, on=keys, how="left")["_fill"].to_numpy()
                idx = X.index[need]
                ok = pd.notna(looked)
                X.loc[idx[ok], col] = looked[ok]
                src.loc[idx[ok]] = "group"
            sources[col] = src
        return (X, sources) if return_source else X

    def fit_transform(self, X, y=None, return_source=False):
        return self.fit(X).transform(X, return_source=return_source)


# ---------------------------------------------------------------------------
# Pipeline dùng ở bước train (Giai đoạn 1: dự báo giá)
# ---------------------------------------------------------------------------
NUMERIC_FEATURES = ["car_age", "odometer", "log_odometer", "miles_per_year", "cylinders_num",
                    "condition_rank", "lat", "long", "n_unknown_specs"]
CATEGORICAL_FEATURES = ["manufacturer", "condition", "fuel", "title_status", "transmission",
                        "drive", "type", "paint_color", "state", "seller_type", "brand_tier"]
HIGH_CARD_FEATURES = ["make_model"]      # vài nghìn giá trị -> gom nhóm hiếm
TEXT_FLAG_PREFIX = "kw_"


def get_feature_lists(df):
    flags = [c for c in df.columns if c.startswith(TEXT_FLAG_PREFIX)]
    extra_num = [c for c in ["desc_len", "has_vin", "manufacturer_inferred"] if c in df.columns]
    return NUMERIC_FEATURES + extra_num + flags, CATEGORICAL_FEATURES, HIGH_CARD_FEATURES


def build_preprocessor(numeric, categorical, high_card, min_frequency=30):
    """ColumnTransformer: impute + scale số; one-hot phân loại; gom nhóm hiếm cho make_model."""
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    num_pipe = Pipeline([("impute", SimpleImputer(strategy="median", add_indicator=True)),
                         ("scale", StandardScaler())])
    cat_pipe = OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=20,
                             sparse_output=True)
    high_pipe = OneHotEncoder(handle_unknown="infrequent_if_exist",
                              min_frequency=min_frequency, sparse_output=True)
    return ColumnTransformer([("num", num_pipe, numeric),
                              ("cat", cat_pipe, categorical),
                              ("high", high_pipe, high_card)])
