"""
13_build_feature_schema.py - A04: CHỌN THUỘC TÍNH ĐẦU VÀO VÀ TẠO feature_schema.json

Nguyên tắc chọn: một cột chỉ được dùng cho mô hình nếu LÚC CHẠY ỨNG DỤNG có được giá trị của nó,
tức là (a) người dùng nhập trên form PyQt6, hoặc (b) hệ thống tính được từ những gì người dùng nhập.
Cột nào chỉ có trong dữ liệu Craigslist (mô tả tin đăng, VIN, tọa độ, loại người bán...) thì bỏ,
vì khi dự đoán cho người dùng thật sẽ không có giá trị để đưa vào mô hình.

Phần QUYẾT ĐỊNH (chọn cột nào, vì sao) viết tay trong các dict bên dưới.
Phần SỐ LIỆU (danh sách giá trị cho dropdown, min/max, giá trị mặc định) lấy tự động từ TẬP TRAIN
(data/splits/train_ids.csv, tạo bởi 12_split_data.py) để khớp với những gì mô hình đã học.

Đầu vào : data/processed/vehicles_filled.pkl, data/splits/train_ids.csv
Đầu ra  : src/features/feature_schema.json

Chạy: python 13_build_feature_schema.py   (chạy SAU 12_split_data.py)
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # thư mục gốc repo
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import pandas as pd

from src import config
from src.features.preprocessing import CONDITION_ORDER

OUT_JSON = config.PROJECT_DIR / "src" / "features" / "feature_schema.json"
TRAIN_IDS = config.DATA_DIR / "splits" / "train_ids.csv"
SPEC = ["drive", "cylinders", "type", "fuel", "transmission"]
MIN_MODEL_COUNT = 20      # dòng xe có < 20 tin trong train thì không đưa vào dropdown

# ---------------------------------------------------------------------------
# 1. NHÃN TIẾNG VIỆT cho giá trị hiển thị trên form (giá trị gửi vào mô hình vẫn là tiếng Anh)
# ---------------------------------------------------------------------------
LABELS_VI = {
    "condition": {"new": "Mới", "like new": "Như mới", "excellent": "Rất tốt", "good": "Tốt",
                  "fair": "Trung bình", "salvage": "Hư hỏng nặng", "unknown": "Không rõ"},
    "fuel": {"gas": "Xăng", "diesel": "Dầu diesel", "hybrid": "Hybrid", "electric": "Điện",
             "other": "Khác", "unknown": "Không rõ"},
    "transmission": {"automatic": "Tự động", "manual": "Số sàn", "other": "Khác", "unknown": "Không rõ"},
    "drive": {"fwd": "Cầu trước (FWD)", "rwd": "Cầu sau (RWD)", "4wd": "4 bánh (4WD/AWD)",
              "unknown": "Không rõ"},
    "type": {"sedan": "Sedan", "suv": "SUV", "pickup": "Bán tải", "truck": "Xe tải nhẹ",
             "coupe": "Coupe", "hatchback": "Hatchback", "wagon": "Wagon", "van": "Van",
             "mini-van": "Minivan", "convertible": "Mui trần", "offroad": "Địa hình",
             "other": "Khác", "unknown": "Không rõ"},
    "title_status": {"clean": "Sạch", "rebuilt": "Đã phục hồi", "salvage": "Từng bị tai nạn nặng",
                     "lien": "Đang thế chấp", "missing": "Mất giấy tờ", "parts only": "Chỉ bán phụ tùng",
                     "unknown": "Không rõ"},
    "paint_color": {"white": "Trắng", "black": "Đen", "silver": "Bạc", "grey": "Xám", "blue": "Xanh dương",
                    "red": "Đỏ", "green": "Xanh lá", "brown": "Nâu", "yellow": "Vàng", "orange": "Cam",
                    "purple": "Tím", "custom": "Màu khác", "unknown": "Không rõ"},
}

# ---------------------------------------------------------------------------
# 2. THUỘC TÍNH NGƯỜI DÙNG NHẬP (khớp từng ô trên Màn hình 2 của autowise.ui)
#    default: giá trị dùng khi người dùng để trống ô không bắt buộc
#      "unknown"    -> dữ liệu train có nhóm 'unknown' (người bán bỏ trống) nên mô hình đã học nhóm này
#      "train_mode" -> cột gần như không có 'unknown' trong train, dùng giá trị phổ biến nhất
# ---------------------------------------------------------------------------
INPUT_FEATURES = [
    # name, nhãn trên form, nhóm trên form, widget, bắt buộc, dùng cho, mặc định
    ("manufacturer", "Hãng xe", "1. Thông tin cơ bản", "QComboBox", True, ["price", "recommendation"], None),
    ("model_base", "Dòng xe", "1. Thông tin cơ bản", "QComboBox", True, ["price", "recommendation"], None),
    ("year", "Năm sản xuất", "1. Thông tin cơ bản", "QSpinBox", True, ["price", "recommendation"], 2018),
    ("type", "Kiểu dáng", "1. Thông tin cơ bản", "QComboBox", True, ["price", "recommendation"], None),
    ("odometer", "Số miles đã đi", "2. Thông số kỹ thuật", "QSpinBox", True, ["price", "recommendation"], 60000),
    ("condition", "Tình trạng xe", "2. Thông số kỹ thuật", "QComboBox", True, ["price", "recommendation"], None),
    ("fuel", "Nhiên liệu", "2. Thông số kỹ thuật", "QComboBox", True, ["price", "recommendation"], None),
    ("transmission", "Hộp số", "2. Thông số kỹ thuật", "QComboBox", True, ["price", "recommendation"], None),
    ("budget_max_usd", "Ngân sách tối đa (USD)", "3. Ngân sách", "QSpinBox", True, ["recommendation"], 20000),
    ("drive", "Hệ dẫn động", "Tùy chọn nâng cao", "QComboBox", False, ["price", "recommendation"], "unknown"),
    ("cylinders", "Số xi-lanh", "Tùy chọn nâng cao", "QComboBox", False, ["price"], "unknown"),
    ("paint_color", "Màu xe", "Tùy chọn nâng cao", "QComboBox", False, ["price"], "unknown"),
    ("title_status", "Tình trạng giấy tờ", "Tùy chọn nâng cao", "QComboBox", False, ["price"], "train_mode"),
    ("state", "Bang tại Mỹ", "Tùy chọn nâng cao", "QComboBox", False, ["price"], "train_mode"),
]

# ---------------------------------------------------------------------------
# 3. THUỘC TÍNH HỆ THỐNG TỰ TÍNH (cùng công thức với add_features() trong preprocessing.py)
# ---------------------------------------------------------------------------
DERIVED_FEATURES = [
    ("car_age", "numeric", ["year"], f"max(0, {config.SCRAPE_YEAR} - year)"),
    ("log_odometer", "numeric", ["odometer"], "log(1 + odometer)"),
    ("miles_per_year", "numeric", ["odometer", "year"], "odometer / max(1, car_age)"),
    ("cylinders_num", "numeric", ["cylinders"], "số trong chuỗi cylinders ('6 cylinders' -> 6), 'unknown' -> NaN"),
    ("condition_rank", "numeric", ["condition"], f"bảng thứ bậc {CONDITION_ORDER}, 'unknown' -> NaN"),
    ("brand_tier", "categorical", ["manufacturer"], "exotic / luxury / mainstream theo danh sách hãng"),
    ("make_model", "categorical", ["manufacturer", "model_base"], "manufacturer + ' ' + model_base"),
]

# ---------------------------------------------------------------------------
# 4. CỘT KHÔNG DÙNG LÀM ĐẦU VÀO MÔ HÌNH (kèm lý do, đưa vào báo cáo)
# ---------------------------------------------------------------------------
EXCLUDED = {
    "price, log_price": "Biến mục tiêu (y), không phải đầu vào",
    "id": "Mã tin đăng, chỉ dùng để ghép bảng và chia tập",
    "desc_missing, desc_len, desc_words, kw_*": "Lấy từ phần mô tả tin đăng; form không có ô nhập mô tả",
    "has_vin, vin_trim, vin_displacement_l, vin_engine_hp, vin_doors, vin_decoded":
        "Cần số VIN; form không có ô VIN và chỉ 48% tin có VIN giải mã được",
    "seller_type": "Người dùng định giá một chiếc xe, không có khái niệm đại lý/chính chủ trên form "
                   "(nếu nhóm muốn giữ, cần thêm ô chọn trên form)",
    "lat, long": "Form chỉ có Bang; tọa độ chi tiết không nhập được",
    "region": "Khu vực Craigslist, trùng ý nghĩa với state và người dùng không biết",
    "posting_date, posting_dow": "Thời điểm đăng tin, không có ý nghĩa khi người dùng định giá",
    "n_unknown_specs": "Trong dữ liệu là số ô người bán bỏ trống; trên app ý nghĩa khác (người dùng không biết)",
    "manufacturer_inferred, vin_make_conflict, vin_year_conflict": "Cờ kỹ thuật của bước làm sạch / giải mã VIN",
    "model": "Tên model gốc viết tự do (20.584 giá trị); dùng model_base đã chuẩn hóa",
    "*_filled, *_source": "Chỉ dùng lúc huấn luyện để tạo 5 cột thông số (xem ghi chú training_notes)",
}


def build_schema(train):
    # Dropdown dòng xe phụ thuộc hãng (dùng cho E02 - vehicle_controller.py)
    mm = train.groupby(["manufacturer", "model_base"], observed=True).size()
    mm = mm[mm >= MIN_MODEL_COUNT].reset_index(name="n")
    model_options = {m: sorted(g["model_base"].tolist())
                     for m, g in mm.groupby("manufacturer", observed=True)}

    features = []
    for name, label, group, widget, required, used_in, default in INPUT_FEATURES:
        f = {"name": name, "source": "user_input", "ui_label": label, "ui_group": group,
             "widget": widget, "required": required, "used_in": used_in}
        if name == "budget_max_usd":
            f.update(dtype="numeric", min=float(config.PRICE_MIN), max=float(config.PRICE_MAX),
                     step=500, default=default,
                     note="Không đưa vào mô hình dự đoán giá; dùng làm điều kiện lọc bắt buộc price <= ngân sách")
        elif name == "year":
            f.update(dtype="numeric", min=config.YEAR_MIN, max=config.YEAR_MAX, step=1, default=default)
        elif name == "odometer":
            f.update(dtype="numeric", min=0, max=config.ODOMETER_MAX, step=1000, default=default,
                     unit="miles")
        elif name == "model_base":
            f.update(dtype="categorical", depends_on="manufacturer",
                     note="Danh sách thay đổi theo hãng, xem options.model_base_by_manufacturer")
        else:
            counts = train[name].value_counts()
            values = counts.index.tolist()
            if default == "train_mode":
                default = str(train.loc[train[name] != "unknown", name].mode()[0])
            # allowed_values: mọi giá trị mô hình đã thấy; ui_options: giá trị hiện trên dropdown
            ui = [v for v in values if v != "unknown"]
            if name == "manufacturer":          # chỉ hiện hãng có ít nhất 1 dòng xe trong dropdown
                ui = [v for v in ui if v in model_options]
            if name == "title_status":
                ui = [v for v in ui if v != "parts only"]   # xe chỉ bán phụ tùng: ngoài phạm vi định giá
            f.update(dtype="categorical", allowed_values=values, ui_options=ui, default=default,
                     value_counts_train={k: int(v) for k, v in counts.items()})
            if name in SPEC:
                f["if_blank"] = ("GroupModeImputer (fit trên train) suy ra từ make_model + year; "
                                 "không suy ra được thì 'unknown'")
            if name in LABELS_VI:
                f["labels_vi"] = {v: LABELS_VI[name].get(v, v) for v in values}
        features.append(f)

    for name, dtype, from_cols, formula in DERIVED_FEATURES:
        features.append({"name": name, "source": "derived", "dtype": dtype,
                         "derived_from": from_cols, "formula": formula, "used_in": ["price"]})

    numeric =["car_age", "odometer", "log_odometer", "miles_per_year", "cylinders_num", "condition_rank"]
    categorical = ["manufacturer", "type", "condition", "fuel", "transmission", "drive",
                   "paint_color", "title_status", "state", "brand_tier"]
    high_card = ["make_model"]
    return {
        "schema_version": "1.0",
        "created": date.today().isoformat(),
        "data_file": "data/processed/vehicles_filled.pkl",
        "split_files": ["data/splits/train_ids.csv", "data/splits/val_ids.csv", "data/splits/test_ids.csv"],
        "values_computed_on": "train split",
        "target": {"name": "log_price", "formula": "log(1 + price)",
                   "inverse": "np.expm1(prediction)", "unit": "USD"},
        "price_model_columns": {
            "numeric": numeric,
            "categorical": categorical,
            "high_cardinality": high_card,
            "all": numeric + categorical + high_card,
        },
        "recommendation_columns": {
            "hard_filters": {"price": "price <= budget_max_usd"},
            "similarity_numeric": ["price", "car_age", "odometer"],
            "similarity_categorical": ["type", "fuel", "transmission", "drive", "condition", "manufacturer"],
            "display": ["id", "manufacturer", "model_base", "year", "price", "odometer", "type",
                        "condition", "fuel", "transmission", "image_path"],
            "note": "image_path do C01 tạo khi ghép ảnh; trọng số từng cột do C03 quyết định",
        },
        "features": features,
        "options": {"model_base_by_manufacturer": model_options,
                    "min_listings_per_model": MIN_MODEL_COUNT},
        "excluded_columns": EXCLUDED,
        "training_notes": [
            "5 cột drive, cylinders, type, fuel, transmission: lấy *_filled khi *_source thuộc {listing, vin}, "
            "còn lại để 'unknown', rồi GroupModeImputer fit trên TẬP TRAIN (cấu hình C trong 09_fill_experiment.py)",
            "Tập dữ liệu gốc có cột desc_len, kw_*, seller_type, lat, long; mốc MAE 2.094 USD có dùng các cột này. "
            "Mô hình chỉ dùng cột trên form cần đo lại mốc mới.",
            "Ô nâng cao để trống: drive, cylinders đặt 'unknown' rồi cho qua GroupModeImputer đã fit (lưu kèm "
            "pipeline); paint_color giữ 'unknown'; title_status, state dùng giá trị 'default'",
            "Kết quả kiểm chứng bộ cột (tập validation): reports/feature_selection.csv, script 14_feature_check.py",
        ],
    }


def validate(schema, df):
    """Kiểm tra mọi cột mô hình cần đều có trong dữ liệu (sau khi tính đặc trưng)."""
    missing = [c for c in schema["price_model_columns"]["all"] if c not in df.columns]
    assert not missing, f"Các cột không có trong dữ liệu: {missing}"
    for f in schema["features"]:
        if f.get("required") and f["dtype"] == "categorical" and f["name"] != "model_base":
            assert f["allowed_values"], f"{f['name']} không có giá trị nào"
    print(f"Kiểm tra: {len(schema['price_model_columns']['all'])} cột của mô hình giá đều có trong dữ liệu -> OK")


def main():
    df = pd.read_pickle(config.PROCESSED_DIR / "vehicles_filled.pkl")
    # 5 cột thông số: dùng giá trị người bán + VIN (không dùng phần điền theo nhóm trên toàn bộ dữ liệu)
    for c in SPEC:
        df[c] = df[f"{c}_filled"].where(df[f"{c}_source"].isin(["listing", "vin"]), "unknown")
    if not TRAIN_IDS.exists():
        raise SystemExit("Chưa có data/splits/train_ids.csv -> chạy 12_split_data.py trước")
    train = df[df["id"].isin(pd.read_csv(TRAIN_IDS)["id"])]
    print(f"Tập train: {len(train):,} dòng")

    schema = build_schema(train)
    validate(schema, df)
    OUT_JSON.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")

    n_models = sum(len(v) for v in schema["options"]["model_base_by_manufacturer"].values())
    print(f"==> Đã lưu {OUT_JSON}")
    print(f"   Mô hình giá dùng {len(schema['price_model_columns']['all'])} cột; "
          f"dropdown: {len(schema['options']['model_base_by_manufacturer'])} hãng, {n_models} dòng xe")


if __name__ == "__main__":
    main()
