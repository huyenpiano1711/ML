"""
cleaning.py - Các hàm làm sạch dữ liệu.

Nguyên tắc:
  1. Mỗi bước là một hàm riêng, nhận DataFrame và trả về DataFrame mới.
  2. Mỗi bước loại dòng đều được ghi vào CleaningLog (trước/sau/bị loại/lý do)
     -> báo cáo được "dữ liệu đi đâu" và double-check rằng tổng số dòng khớp.
  3. Không fit bất kỳ thứ gì phụ thuộc vào tập test (scaler, encoder, imputer
     theo thống kê...). Những việc đó làm trong Pipeline lúc train để tránh rò rỉ.
"""
import re

import numpy as np
import pandas as pd

from src import config


class CleaningLog:
    """Ghi lại số dòng trước/sau mỗi bước làm sạch."""

    def __init__(self, n_start):
        self.n_start = n_start
        self.rows = []

    def record(self, step, before, after, reason):
        removed = before - after
        self.rows.append({"buoc": step, "so_dong_truoc": before, "so_dong_sau": after,
                          "bi_loai": removed, "pct_loai_so_voi_goc": round(removed / self.n_start * 100, 2),
                          "ly_do": reason})
        print(f"[{step}] {before:,} -> {after:,}  (loại {removed:,})  {reason}")

    def to_frame(self):
        return pd.DataFrame(self.rows)

    def check_consistency(self, n_final):
        """Double-check: số dòng cuối = số dòng đầu - tổng số dòng bị loại."""
        total_removed = sum(r["bi_loai"] for r in self.rows)
        assert self.n_start - total_removed == n_final, (
            f"Lệch số dòng! đầu {self.n_start} - loại {total_removed} != cuối {n_final}")
        # Các bước phải nối tiếp nhau: 'sau' của bước i == 'trước' của bước i+1
        for a, b in zip(self.rows, self.rows[1:]):
            assert a["so_dong_sau"] == b["so_dong_truoc"], f"Đứt mạch giữa {a['buoc']} và {b['buoc']}"
        print(f"   [OK] Log nhất quán: {self.n_start:,} - {total_removed:,} = {n_final:,}")


def _filter(df, mask, log, step, reason):
    before = len(df)
    out = df.loc[mask].copy()
    log.record(step, before, len(out), reason)
    return out


# ---------------------------------------------------------------------------
# A. CHUẨN HÓA KIỂU & CHUỖI (không loại dòng)
# ---------------------------------------------------------------------------
STRING_COLS = ["region", "manufacturer", "model", "condition", "cylinders", "fuel",
               "title_status", "transmission", "drive", "size", "type", "paint_color", "state"]


def vin_is_valid(vin):
    """VIN chuẩn (xe từ 1981): đúng 17 ký tự, không chứa I/O/Q, không phải chuỗi lặp
    vài ký tự (11111..., 131313...). Trả về Series bool (NA -> False)."""
    v = vin.astype("string")
    ok = v.str.fullmatch(r"[A-HJ-NPR-Z0-9]{17}").fillna(False)
    low_diversity = v.map(lambda s: isinstance(s, str) and len(set(s)) <= 3)
    return (ok & ~low_diversity.astype(bool)).astype(bool)


def standardize_types(df):
    df = df.copy()
    for c in STRING_COLS:
        df[c] = df[c].astype("string").str.strip().str.lower()
        df[c] = df[c].replace({"": pd.NA})
    df["VIN"] = df["VIN"].astype("string").str.strip().str.upper()
    # VIN rác (vd '13131313131313131', '00000000000000000', VIN 11 ký tự...) -> coi như không có VIN.
    # Nếu giữ lại, bước khử trùng theo VIN sẽ gộp nhầm nhiều xe KHÁC NHAU dùng chung 1 VIN rác.
    valid = vin_is_valid(df["VIN"])
    n_bad = int((df["VIN"].notna() & ~valid).sum())
    df.loc[~valid, "VIN"] = pd.NA
    print(f"   VIN không hợp lệ -> đặt NA: {n_bad:,} dòng")
    df["posting_date"] = pd.to_datetime(df["posting_date"], utc=True, errors="coerce")
    # Loại người bán lấy từ URL: .../ctd/... = car-truck by dealer, .../cto/... = by owner
    df["seller_type"] = df["url"].str.extract(r"/(ct[od])/")[0].map({"ctd": "dealer", "cto": "owner"})
    # Hợp nhất 'rover' và 'land rover' (cùng một hãng)
    df["manufacturer"] = df["manufacturer"].replace({"rover": "land rover"})
    return df


# ---------------------------------------------------------------------------
# B. SUY RA HÃNG XE TỪ TÊN MODEL (cứu ~4% dòng thiếu manufacturer)
# ---------------------------------------------------------------------------
# Từ khóa xuất hiện ở đầu cột model -> hãng tương ứng
BRAND_ALIASES = {
    "chevy": "chevrolet", "chev": "chevrolet", "vw": "volkswagen", "volkswagon": "volkswagen",
    "mercedes": "mercedes-benz", "benz": "mercedes-benz", "mercedes-benz": "mercedes-benz",
    "landrover": "land rover", "range": "land rover", "infinity": "infiniti",
    "alfa": "alfa-romeo", "aston": "aston-martin", "rolls": "rolls-royce", "rolls-royce": "rolls-royce",
    "lamborghini": "lamborghini", "mclaren": "mclaren", "maserati": "maserati", "bentley": "bentley",
    "genesis": "genesis", "hummer": "hummer", "scion": "scion", "isuzu": "isuzu", "suzuki": "suzuki",
    "oldsmobile": "oldsmobile", "plymouth": "plymouth", "saab": "saab", "smart": "smart",
    "lotus": "lotus", "polestar": "polestar", "rivian": "rivian",
}


def infer_manufacturer(df, known_brands):
    """Nếu manufacturer thiếu, thử lấy từ 1-2 từ đầu tiên của model."""
    df = df.copy()
    miss = df["manufacturer"].isna() & df["model"].notna()
    lookup = {b: b for b in known_brands}
    lookup.update(BRAND_ALIASES)
    lookup.pop("rover", None)       # 'range rover' xử lý qua alias 'range'

    def guess(m):
        toks = re.sub(r"[^a-z0-9\- ]", " ", m).split()
        if not toks:
            return pd.NA
        if len(toks) >= 2 and f"{toks[0]} {toks[1]}" in lookup:   # 'land rover', 'alfa romeo'
            return lookup[f"{toks[0]} {toks[1]}"]
        if toks[0] == "range" and (len(toks) < 2 or toks[1] != "rover"):
            return pd.NA                                             # 'range' không đi kèm rover
        return lookup.get(toks[0], pd.NA)

    guessed = df.loc[miss, "model"].map(guess)
    df.loc[miss, "manufacturer"] = guessed
    df["manufacturer_inferred"] = 0
    df.loc[miss & df["manufacturer"].notna(), "manufacturer_inferred"] = 1
    print(f"   suy ra được hãng cho {int(df['manufacturer_inferred'].sum()):,}/{int(miss.sum()):,} dòng thiếu manufacturer")
    return df


# ---------------------------------------------------------------------------
# C. CHUẨN HÓA TÊN DÒNG XE (model -> model_base)
# ---------------------------------------------------------------------------
# Từ đầu tiên của các dòng xe gồm 2 từ
MULTI_WORD_FIRST = {"grand", "super", "santa", "range", "monte", "park", "land", "model",
                    "town", "new", "el", "le", "town&country", "sport"}
FILLER = {"new", "used", "the", "certified", "preowned", "allnew", "all",
          "pickup", "diesel", "deisel", "cummins", "lifted", "4x4", "4wd", "awd", "hemi", "v6", "v8"}
MANUF_WORDS = {"chevy", "chevrolet", "benz", "mercedes", "mercedes-benz", "vw", "volkswagen",
               "ford", "toyota", "honda", "nissan", "dodge", "gmc", "bmw", "jeep", "ram", "kia",
               "hyundai", "mazda", "subaru", "audi", "lexus", "acura", "buick", "cadillac",
               "chrysler", "lincoln", "infiniti", "volvo", "mitsubishi", "porsche", "tesla",
               "mini", "fiat", "jaguar"}
# (Không đưa 'land' vào đây để giữ được 'land cruiser' của Toyota; với hãng
#  'land rover' thì các từ 'land', 'rover' được thêm động từ tên hãng.)


def normalize_model(model, manufacturer):
    """'Silverado 1500 LT 4x4' -> 'silverado'; 'F-150 XLT' và 'f150' -> 'f150';
    'Grand Cherokee Limited' -> 'grand cherokee'; 'Benz E350' -> 'e350'."""
    if not isinstance(model, str):
        return pd.NA
    if not isinstance(manufacturer, str):      # pd.NA / NaN -> None để so sánh an toàn
        manufacturer = None
    s = model.lower().replace("&", " ").replace("-", "")
    s = re.sub(r"\b\d\.\d[a-z]*\b", " ", s)         # bỏ dung tích động cơ '3.2', '5.7l' ('3.2 tl' -> 'tl')
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    toks = [t for t in s.split() if t]
    man_words = set(MANUF_WORDS)
    if isinstance(manufacturer, str):
        man_words |= set(manufacturer.replace("-", " ").split()) | {manufacturer.replace("-", "")}
    # bỏ các từ thừa / tên hãng / năm (vd '2015') ở đầu chuỗi
    while toks and (toks[0] in FILLER or toks[0] in man_words or re.fullmatch(r"(19|20)\d\d", toks[0])):
        # giữ lại 'ram 1500' khi hãng là dodge, 'rover' khi đứng sau 'range'
        if toks[0] == "ram" and manufacturer == "dodge":
            break
        toks = toks[1:]
    if not toks:
        return pd.NA
    special = _brand_specific(toks, manufacturer)
    if special is not None:
        return special
    first, nxt = toks[0], (toks[1] if len(toks) > 1 else "")
    # Tên bị tách thành 1 chữ cái + phần còn lại (kiểm tra từ dữ liệu):
    #   'f 350' -> 'f350', 'c/k 1500' -> 'ck', 'g g37x' -> 'g37x', '4 runner' -> '4runner'
    # (Không gộp chữ số đứng một mình như Mazda '3', '6' vì đó là tên thật của dòng xe.)
    if len(first) == 1 and first.isalpha() and nxt:
        if nxt[0].isdigit() or len(nxt) == 1:
            return first + nxt
        if nxt.startswith(first):
            return nxt
    if first == "4" and nxt == "runner":
        return "4runner"
    if first == "towncar":
        return "town car"
    if first in MULTI_WORD_FIRST and nxt:
        if first == "town":                      # Lincoln Town Car vs Chrysler Town & Country
            return "town car" if nxt == "car" else "town country"
        return f"{first} {nxt}"
    return first


_MB_CLASS = {"c": "c-class", "e": "e-class", "s": "s-class", "ml": "m-class", "m": "m-class",
             "gl": "gl-class", "g": "g-class", "sl": "sl-class"}


def _brand_specific(toks, manufacturer):
    """Quy tắc riêng cho vài hãng có cách đặt tên đặc biệt (kiểm tra từ EDA).
    Trả về None nếu không áp dụng quy tắc nào."""
    first, nxt = toks[0], (toks[1] if len(toks) > 1 else "")
    if manufacturer == "land rover":
        # Bộ dữ liệu gốc đã "nuốt" chữ 'range rover' -> 'sport', 'evoque', 'hse'...
        if first == "discovery":
            return "discovery sport" if nxt == "sport" else "discovery"
        if first == "range":
            first, nxt = nxt, (toks[2] if len(toks) > 2 else "")
        if first in {"sport", "evoque", "velar"}:
            return f"range rover {first}"
        if first in {"hse", "supercharged", "autobiography", "rover"}:
            return "range rover"
    if manufacturer == "tesla":
        if first == "model" and nxt:
            return f"model {nxt[0]}"          # 'model s p85' -> 'model s'
        if first in {"s", "3", "x", "y"}:
            return f"model {first}"
    if manufacturer == "mercedes-benz":
        m = re.fullmatch(r"([a-z]{1,3})class", first)
        if m:
            return _MB_CLASS.get(m.group(1), f"{m.group(1)}-class")
        m = re.fullmatch(r"([a-z]{1,3})(\d{2,3})[a-z]*", first)
        if m or (first in _MB_CLASS and nxt.isdigit()):
            letters = m.group(1) if m else first
            # 'e350' -> 'e-class', 'r350' -> 'r-class', 'glk350' -> 'glk'
            return _MB_CLASS.get(letters, f"{letters}-class" if len(letters) == 1 else letters)
    if manufacturer == "bmw":
        m = re.fullmatch(r"([1-8])(?:series|\d\d[a-z]*)?", first)
        if m:
            return f"{m.group(1)} series"            # '328i', '3series', '3' -> '3 series'
    return None


def infer_manufacturer_learned(df, min_count=30, min_purity=0.95):
    """Lần suy luận thứ 2: học từ chính dữ liệu bảng 'dòng xe -> hãng'.
    Vd 'f150' xuất hiện 7.000 lần và 100% là ford -> tin thiếu hãng ghi 'f150' => ford.
    Chỉ dùng các dòng xe có >= min_count tin và >= 95% thuộc một hãng duy nhất.
    (Ánh xạ chỉ dùng tên xe, không dùng giá -> không rò rỉ biến mục tiêu.)"""
    df = df.copy()
    known = df[df["manufacturer"].notna() & df["model_base"].notna()]
    tab = known.groupby("model_base")["manufacturer"].agg(
        n="size", top=lambda s: s.value_counts().index[0], share=lambda s: s.value_counts(normalize=True).iloc[0])
    mapping = tab[(tab["n"] >= min_count) & (tab["share"] >= min_purity)]["top"].to_dict()

    miss = df["manufacturer"].isna() & df["model"].notna()
    base_guess = df.loc[miss, "model"].map(lambda m: normalize_model(m, None))
    guessed = base_guess.map(lambda b: mapping.get(b, pd.NA) if isinstance(b, str) else pd.NA)
    hit = guessed.notna()
    idx = guessed[hit].index
    df.loc[idx, "manufacturer"] = guessed[hit]
    df.loc[idx, "manufacturer_inferred"] = 2          # 2 = suy ra bằng bảng học từ dữ liệu
    # tính lại model_base cho các dòng vừa có hãng (vì có quy tắc riêng theo hãng)
    df.loc[idx, "model_base"] = [normalize_model(m, mf) for m, mf in
                                 zip(df.loc[idx, "model"], df.loc[idx, "manufacturer"])]
    print(f"   suy luận lần 2 (bảng dòng xe -> hãng, {len(mapping):,} dòng xe): thêm {len(idx):,} dòng")
    return df


def add_model_base(df):
    df = df.copy()
    pairs = df[["model", "manufacturer"]].drop_duplicates()
    pairs["model_base"] = [normalize_model(m, mf) for m, mf in
                           zip(pairs["model"], pairs["manufacturer"])]
    df = df.merge(pairs, on=["model", "manufacturer"], how="left", validate="many_to_one")
    df["model_base"] = df["model_base"].astype("string")
    return df


# ---------------------------------------------------------------------------
# D. LOẠI DÒNG KHÔNG HỢP LỆ
# ---------------------------------------------------------------------------
def _is_placeholder_number(x):
    """11111, 99999, 123456, 1234567... (gõ cho có)."""
    s = str(int(x))
    return (len(s) >= 5 and len(set(s)) == 1) or s in {"12345", "123456", "1234567", "12345678", "123456789"}


def drop_missing_keys(df, log):
    df = _filter(df, df["manufacturer"].notna(), log, "D1_thieu_hang",
                 "Thiếu hãng xe (sau khi đã thử suy ra từ model)")
    df = _filter(df, df["model_base"].notna(), log, "D2_thieu_model", "Thiếu / không đọc được tên dòng xe")
    df = _filter(df, df["year"].notna(), log, "D3_thieu_nam", "Thiếu năm sản xuất")
    df = _filter(df, df["odometer"].notna(), log, "D4_thieu_odo", "Thiếu số dặm đã đi")
    df = _filter(df, ~df["manufacturer"].isin(config.NON_CAR_MANUFACTURERS), log,
                 "D5_khong_phai_oto", "Xe máy (harley-davidson) nằm ngoài phạm vi")
    pattern = r"\b(?:" + "|".join(config.COMMERCIAL_MODEL_WORDS) + r")\b"
    commercial = df["model"].str.contains(pattern, regex=True, na=False) | df["type"].isin(config.NON_CAR_TYPES)
    df = _filter(df, ~commercial, log, "D6_xe_thuong_mai",
                 "Xe tải / xe buýt thương mại (freightliner, international, type = bus...)")
    return df


def drop_invalid_values(df, log):
    df = _filter(df, df["price"].between(config.PRICE_MIN, config.PRICE_MAX), log, "E1_gia_ngoai_khoang",
                 f"price ngoài [{config.PRICE_MIN:,}; {config.PRICE_MAX:,}] (0 = liên hệ, giá trả góp, gõ sai)")
    df = _filter(df, ~df["price"].map(_is_placeholder_number), log, "E2_gia_gia_cho",
                 "Giá dạng 11111 / 12345 (giá trị giữ chỗ)")
    df = _filter(df, df["year"].between(config.YEAR_MIN, config.YEAR_MAX), log, "E3_nam_ngoai_khoang",
                 f"year ngoài [{config.YEAR_MIN}; {config.YEAR_MAX}] (xe cổ có quy luật giá khác)")
    df = _filter(df, df["odometer"] <= config.ODOMETER_MAX, log, "E4_odo_qua_lon",
                 f"odometer > {config.ODOMETER_MAX:,} dặm (gõ sai)")
    df = _filter(df, ~df["odometer"].map(_is_placeholder_number), log, "E5_odo_gia_cho",
                 "odometer dạng 111111 / 123456")
    age = config.SCRAPE_YEAR - df["year"]
    suspicious = (age >= config.OLD_CAR_AGE) & (df["odometer"] < config.ODOMETER_MIN_FOR_OLD_CAR)
    df = _filter(df, ~suspicious, log, "E6_odo_vo_ly",
                 f"Xe >= {config.OLD_CAR_AGE} tuổi nhưng odometer < {config.ODOMETER_MIN_FOR_OLD_CAR} dặm")
    # Xe <= 3 tuổi mà giá < 3.000 USD: gần như chắc chắn là tiền trả góp/tháng hoặc tiền cọc
    # (vd Cadillac XT6 2021 giá 1.040). Phải loại TRƯỚC bước ngoại lai theo nhóm, nếu không
    # các nhóm toàn giá trả góp sẽ kéo trung vị xuống và đánh dấu nhầm giá thật là ngoại lai.
    age = config.SCRAPE_YEAR - df["year"]
    payment = (age <= config.PAYMENT_PRICE_MAX_AGE) & (df["price"] < config.PAYMENT_PRICE_THRESHOLD)
    df = _filter(df, ~payment, log, "E7_gia_tra_gop",
                 f"Xe <= {config.PAYMENT_PRICE_MAX_AGE} tuổi nhưng giá < {config.PAYMENT_PRICE_THRESHOLD:,} (giá trả góp/đặt cọc)")
    return df


# ---------------------------------------------------------------------------
# E. KHỬ TRÙNG LẶP
# ---------------------------------------------------------------------------
CONTENT_KEY = ["manufacturer", "model", "year", "odometer", "price", "condition", "fuel",
               "transmission", "drive", "type", "paint_color", "state", "seller_type"]


def drop_duplicates(df, log):
    # Sắp xếp tin MỚI NHẤT lên đầu -> keep='first' giữ lại tin mới nhất (giá cập nhật nhất)
    df = df.sort_values(["posting_date", "id"], ascending=[False, False], na_position="last")
    has_vin = df["VIN"].notna()
    keep = ~(has_vin & df["VIN"].duplicated(keep="first"))
    df = _filter(df, keep, log, "F1_trung_VIN",
                 "Cùng VIN đăng lại nhiều lần/nhiều khu vực -> giữ tin mới nhất")
    # Với tin KHÔNG có VIN: nếu trùng toàn bộ nội dung chính với một tin khác -> cùng 1 xe đăng lại.
    # Hai tin có 2 VIN KHÁC NHAU thì luôn giữ cả hai (đại lý có thể bán nhiều xe giống hệt nhau).
    # Ưu tiên giữ bản có VIN, sau đó đến bản mới nhất.
    df = df.assign(_has_vin=df["VIN"].notna()).sort_values(
        ["_has_vin", "posting_date", "id"], ascending=[False, False, False], na_position="last")
    dup = df.duplicated(subset=CONTENT_KEY, keep="first") & ~df["_has_vin"]
    df = _filter(df, ~dup, log, "F2_trung_noi_dung",
                 "Tin không VIN trùng toàn bộ thông số + giá + bang với tin khác -> tin đăng lặp")
    df = df.drop(columns="_has_vin")
    return df.sort_values("id").reset_index(drop=True)


# ---------------------------------------------------------------------------
# F. NGOẠI LAI THEO NHÓM (robust z-score trên log giá)
# ---------------------------------------------------------------------------
def drop_group_outliers(df, log):
    """So sánh giá mỗi xe với các xe CÙNG hãng + dòng + năm. Giá lệch quá xa
    (|z| > 3.5) gần như chắc là giá trả góp/đặt cọc, gõ thiếu/thừa số 0."""
    df = df.copy()
    lp = np.log(df["price"])
    g = df.groupby(config.OUTLIER_GROUP_COLS, observed=True)
    n = g["price"].transform("size")
    med = lp.groupby([df[c] for c in config.OUTLIER_GROUP_COLS], observed=True).transform("median")
    mad = (lp - med).abs().groupby([df[c] for c in config.OUTLIER_GROUP_COLS], observed=True).transform("median")
    z = 0.6745 * (lp - med) / mad.clip(lower=config.OUTLIER_MAD_FLOOR)
    df["price_robust_z"] = z.where(n >= config.OUTLIER_MIN_GROUP_SIZE)
    is_out = df["price_robust_z"].abs() > config.OUTLIER_Z_THRESHOLD
    out = df.loc[is_out]
    print(f"   ngoại lai: {int((out['price_robust_z'] < 0).sum()):,} giá quá THẤP, "
          f"{int((out['price_robust_z'] > 0).sum()):,} giá quá CAO so với xe cùng nhóm")
    df = _filter(df, ~is_out, log, "G1_ngoai_lai_nhom",
                 f"|robust z| > {config.OUTLIER_Z_THRESHOLD} so với xe cùng hãng+dòng+năm (nhóm >= {config.OUTLIER_MIN_GROUP_SIZE})")
    return df.drop(columns="price_robust_z"), out


# ---------------------------------------------------------------------------
# G. XỬ LÝ GIÁ TRỊ THIẾU CÒN LẠI (không loại dòng)
# ---------------------------------------------------------------------------
def handle_remaining_missing(df):
    df = df.copy()
    # Biến phân loại: thiếu -> 'unknown'. Việc "người bán không khai" cũng mang thông tin
    # (vd đại lý thường bỏ trống condition), nên giữ thành 1 nhóm riêng thay vì đoán mode.
    for c in ["condition", "cylinders", "fuel", "title_status", "transmission", "drive",
              "type", "paint_color"]:
        df[c] = df[c].fillna("unknown")
    # Tọa độ ngoài nước Mỹ -> NaN (sẽ impute bằng trung vị theo bang khi cần)
    bad = (df["lat"] < 18) | (df["lat"] > 72) | (df["long"] > -65) | (df["long"] < -170)
    df.loc[bad, ["lat", "long"]] = np.nan
    return df
