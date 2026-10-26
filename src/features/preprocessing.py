"""
preprocessing.py - Tạo đặc trưng mới (feature engineering) và dựng Pipeline tiền xử lý
cho giai đoạn train và inference mô hình dự đoán giá AutoWise AI.

Lưu ý quan trọng về RÒ RỈ DỮ LIỆU (data leakage):
  - Các đặc trưng ở hàm add_features() chỉ dùng thông tin của CHÍNH DÒNG ĐÓ
    (tuổi xe, dặm/năm...) -> an toàn khi tạo trước khi chia train/test.
  - Các bước học từ dữ liệu (GroupModeImputer, imputer trung vị, scale, encoder)
    CHỈ được fit trên tập train.
"""
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

from src import config

LUXURY = {"bmw", "mercedes-benz", "audi", "lexus", "cadillac", "acura", "infiniti", "lincoln",
          "volvo", "land rover", "jaguar", "porsche", "tesla", "alfa-romeo", "genesis", "maserati"}
EXOTIC = {"ferrari", "aston-martin", "lamborghini", "mclaren", "bentley", "rolls-royce", "morgan", "lotus"}

CONDITION_ORDER = {"salvage": 0, "fair": 1, "good": 2, "excellent": 3, "like new": 4, "new": 5}

PRICE_MODEL_NUMERIC = [
    "car_age", "odometer", "log_odometer", "miles_per_year", "cylinders_num", "condition_rank"
]
PRICE_MODEL_CATEGORICAL = [
    "manufacturer", "type", "condition", "fuel", "transmission", "drive", "paint_color", "title_status", "state", "brand_tier"
]
PRICE_MODEL_HIGH_CARD = ["make_model"]
ALL_PRICE_MODEL_FEATURES = PRICE_MODEL_NUMERIC + PRICE_MODEL_CATEGORICAL + PRICE_MODEL_HIGH_CARD


def add_features(df):
    """Tính các đặc trưng dẫn xuất từ thuộc tính cơ sở."""
    df = df.copy()
    if "year" in df.columns:
        df["car_age"] = (config.SCRAPE_YEAR - df["year"]).clip(lower=0)
    if "odometer" in df.columns and "car_age" in df.columns:
        df["miles_per_year"] = df["odometer"] / df["car_age"].clip(lower=1)
        df["log_odometer"] = np.log1p(df["odometer"])
    if "price" in df.columns:
        df["log_price"] = np.log1p(df["price"])
    if "cylinders" in df.columns:
        df["cylinders_num"] = pd.to_numeric(df["cylinders"].astype(str).str.extract(r"(\d+)")[0], errors="coerce")
    if "condition" in df.columns:
        df["condition_rank"] = df["condition"].map(CONDITION_ORDER)
    if "manufacturer" in df.columns:
        df["brand_tier"] = np.select(
            [df["manufacturer"].isin(EXOTIC), df["manufacturer"].isin(LUXURY)],
            ["exotic", "luxury"], default="mainstream")
    if "VIN" in df.columns:
        df["has_vin"] = df["VIN"].notna().astype("int8")
    if "manufacturer" in df.columns and "model_base" in df.columns:
        df["make_model"] = df["manufacturer"].astype(str) + " " + df["model_base"].astype(str)
    if "posting_date" in df.columns:
        df["posting_dow"] = pd.to_datetime(df["posting_date"]).dt.dayofweek
    info_cols = ["condition", "cylinders", "drive", "type", "paint_color"]
    if all(c in df.columns for c in info_cols):
        df["n_unknown_specs"] = (df[info_cols] == "unknown").sum(axis=1).astype("int8")
    return df


class FeatureEngineer(BaseEstimator, TransformerMixin):
    """Transformer sklearn để thêm các cột dẫn xuất trong Pipeline."""
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return add_features(X)


class GroupModeImputer(BaseEstimator, TransformerMixin):
    """Điền 'unknown' bằng giá trị phổ biến nhất trong nhóm hãng+dòng+năm, nếu không đủ thì
    nhóm hãng+dòng. Chỉ điền khi nhóm có >= min_n xe đã biết giá trị và >= min_purity xe
    cùng một giá trị (vd 90% Ford F-150 2015 là 4wd thì mới điền 4wd).

    Dùng như một bước của sklearn: fit() CHỈ trên tập train, transform() cho cả train, val và test.
    """
    def __init__(self, cols=None, levels=(("make_model", "year"), ("make_model",)),
                 min_n=10, min_purity=0.9, missing="unknown"):
        self.cols = cols
        self.levels = levels
        self.min_n = min_n
        self.min_purity = min_purity
        self.missing = missing
        self.tables_ = None

    def fit(self, X, y=None):
        cols = list(self.cols) if self.cols is not None else ["drive", "cylinders", "type", "fuel", "transmission"]
        levels = [list(lv) for lv in self.levels]
        self.tables_ = {}
        for col in cols:
            if col not in X.columns:
                continue
            known = X[X[col] != self.missing]
            self.tables_[col] = []
            for keys in levels:
                if not all(k in known.columns for k in keys):
                    continue
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
        cols = list(self.cols) if self.cols is not None else ["drive", "cylinders", "type", "fuel", "transmission"]
        levels = [list(lv) for lv in self.levels]
        sources = {}
        for col in cols:
            if col not in X.columns or col not in self.tables_:
                continue
            src = pd.Series(np.where(X[col] != self.missing, "known", self.missing), index=X.index, dtype="object")
            for keys, table in zip(levels, self.tables_[col]):
                need = X[col] == self.missing
                if not need.any() or not all(k in X.columns for k in keys):
                    break
                looked = X.loc[need, keys].merge(table, on=keys, how="left")["_fill"].to_numpy()
                idx = X.index[need]
                ok = pd.notna(looked)
                X.loc[idx[ok], col] = looked[ok]
                src.loc[idx[ok]] = "group"
            sources[col] = src
        if "cylinders" in X.columns:
            X["cylinders_num"] = pd.to_numeric(X["cylinders"].astype(str).str.extract(r"(\d+)")[0], errors="coerce")
        if "condition" in X.columns:
            X["condition_rank"] = X["condition"].map(CONDITION_ORDER)
        return (X, sources) if return_source else X

    def fit_transform(self, X, y=None, return_source=False):
        return self.fit(X, y).transform(X, return_source=return_source)


def build_preprocessor(numeric=None, categorical=None, high_card=None, min_frequency=30):
    """ColumnTransformer cho linear / tree models: impute + scale số; one-hot phân loại."""
    if numeric is None:
        numeric = PRICE_MODEL_NUMERIC
    if categorical is None:
        categorical = PRICE_MODEL_CATEGORICAL
    if high_card is None:
        high_card = PRICE_MODEL_HIGH_CARD

    num_pipe = Pipeline([
        ("impute", SimpleImputer(strategy="median", add_indicator=True)),
        ("scale", StandardScaler())
    ])
    cat_pipe = OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=20, sparse_output=True)
    high_pipe = OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=min_frequency, sparse_output=True)
    return ColumnTransformer([
        ("num", num_pipe, numeric),
        ("cat", cat_pipe, categorical),
        ("high", high_pipe, high_card)
    ])


def build_hgb_preprocessor(numeric=None, categorical=None, high_card=None, max_categories=250):
    """ColumnTransformer cho HistGradientBoosting: OrdinalEncoder cho categorical, passthrough số."""
    if numeric is None:
        numeric = PRICE_MODEL_NUMERIC
    if categorical is None:
        categorical = PRICE_MODEL_CATEGORICAL
    if high_card is None:
        high_card = PRICE_MODEL_HIGH_CARD

    all_cat = list(categorical) + list(high_card)
    enc = OrdinalEncoder(
        handle_unknown="use_encoded_value",
        unknown_value=-1,
        encoded_missing_value=-1,
        max_categories=max_categories
    )
    # Categorical đặt ở trước (chỉ số 0 .. len(all_cat)-1), numeric ở sau
    prep = ColumnTransformer([
        ("cat", enc, all_cat),
        ("num", "passthrough", list(numeric))
    ])
    cat_indices = list(range(len(all_cat)))
    return prep, cat_indices
