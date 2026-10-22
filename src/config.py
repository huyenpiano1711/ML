"""
config.py - Cấu hình chung cho toàn bộ dự án AutoWise AI.

Mọi đường dẫn và ngưỡng làm sạch dữ liệu đều đặt ở đây để:
  - Dễ chỉnh sửa (không phải sửa trong từng file code).
  - Dễ trình bày trong báo cáo (mỗi ngưỡng đều có lý do đi kèm).
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. ĐƯỜNG DẪN
# ---------------------------------------------------------------------------
# Thư mục gốc của repo (chứa data/, scripts/, src/, reports/)
PROJECT_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_DIR / "data"
# File dữ liệu gốc (Craigslist Cars & Trucks - Kaggle). Nếu để ở chỗ khác, sửa dòng này.
RAW_CSV = DATA_DIR / "raw" / "vehicles.csv"
INTERIM_DIR = DATA_DIR / "interim"          # dữ liệu trung gian (đặc trưng từ mô tả)
PROCESSED_DIR = DATA_DIR / "processed"      # dữ liệu sạch dùng để train
REPORT_DIR = PROJECT_DIR / "reports"
EDA_RAW_DIR = REPORT_DIR / "eda_raw"        # biểu đồ + thống kê trên dữ liệu gốc
EDA_CLEAN_DIR = REPORT_DIR / "eda_clean"    # biểu đồ + thống kê sau làm sạch

DESC_FEATURES_CSV = INTERIM_DIR / "desc_features.csv"
CLEAN_CSV = PROCESSED_DIR / "vehicles_clean.csv"
CLEAN_PKL = PROCESSED_DIR / "vehicles_clean.pkl"   # đọc nhanh hơn CSV rất nhiều
CLEANING_LOG_CSV = REPORT_DIR / "cleaning_log.csv"
DATA_DICT_CSV = REPORT_DIR / "data_dictionary.csv"

IMAGE_DIR = PROJECT_DIR / "assets" / "car_images_unique"   # ảnh minh họa đã khử trùng

for _d in (INTERIM_DIR, PROCESSED_DIR, EDA_RAW_DIR, EDA_CLEAN_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# 2. CỘT DỮ LIỆU
# ---------------------------------------------------------------------------
# Cột 'description' chiếm phần lớn dung lượng file (~1.4 GB) nên KHÔNG đọc chung;
# nó được xử lý riêng theo từng khối (chunk) trong 02_extract_text_features.py.
# 'image_url', 'region_url' không có giá trị cho mô hình -> không đọc.
RAW_USECOLS = [
    "id", "url", "region", "price", "year", "manufacturer", "model",
    "condition", "cylinders", "fuel", "odometer", "title_status",
    "transmission", "VIN", "drive", "size", "type", "paint_color",
    "county", "state", "lat", "long", "posting_date",
]

CATEGORICAL_LOW_CARD = [
    "condition", "cylinders", "fuel", "title_status", "transmission",
    "drive", "size", "type", "paint_color",
]

# ---------------------------------------------------------------------------
# 3. NGƯỠNG LÀM SẠCH (mỗi ngưỡng có lý do - ghi vào báo cáo chương 4)
# ---------------------------------------------------------------------------
# Dữ liệu được crawl từ 04/2021 đến 05/2021 -> dùng 2021 làm "năm quan sát"
# để tính tuổi xe. (Được kiểm tra lại từ cột posting_date trong EDA.)
SCRAPE_YEAR = 2021

# Giá: price = 0 hoặc rất thấp thường là "liên hệ để biết giá" hoặc giá trả góp
# hàng tháng/tiền đặt cọc của đại lý, không phải giá bán. Giá > 150k chủ yếu là
# siêu xe hoặc gõ sai (1234567, 3.7 tỷ USD...). Ứng dụng nhắm tới người mua phổ thông.
PRICE_MIN = 1_000
PRICE_MAX = 150_000

# Năm sản xuất: xe trước 1990 là xe cổ/sưu tầm, giá tăng theo tuổi (ngược với
# quy luật khấu hao) -> nằm ngoài phạm vi đề tài.
YEAR_MIN = 1990
YEAR_MAX = 2022          # xe đời 2022 đã được bán từ giữa 2021

# Số km (dặm) đã đi: > 400k gần như chắc chắn là gõ sai (1111111, 9999999...).
ODOMETER_MAX = 400_000
# Xe đã >= 2 tuổi mà odometer < 100 dặm -> giá trị giữ chỗ (0, 1, 10...).
ODOMETER_MIN_FOR_OLD_CAR = 100
OLD_CAR_AGE = 2
# Xe gần như mới (<= 3 tuổi) mà giá < 3.000 USD -> giá trả góp/tháng hoặc tiền cọc.
PAYMENT_PRICE_MAX_AGE = 3
PAYMENT_PRICE_THRESHOLD = 3_000

# Loại bỏ giá ngoại lai theo nhóm (cùng hãng + dòng xe + năm) bằng robust z-score:
#   z = 0.6745 * (log(price) - median) / MAD
# |z| > 3.5 là ngưỡng chuẩn của Iglewicz & Hoaglin (1993).
OUTLIER_GROUP_COLS = ["manufacturer", "model_base", "year"]
OUTLIER_MIN_GROUP_SIZE = 10
OUTLIER_Z_THRESHOLD = 3.5
# Sàn cho MAD (đơn vị log giá). Nếu một nhóm toàn tin đăng lặp cùng 1 giá thì MAD ~ 0
# và z bùng nổ (|z| hàng trăm) cho cả những giá bình thường. Với sàn 0.15, một xe chỉ
# bị coi là ngoại lai khi giá lệch > ~2.2 lần (hoặc < ~0.46 lần) trung vị nhóm.
OUTLIER_MAD_FLOOR = 0.15

# Ngoài phạm vi "xe con cho người mua phổ thông":
NON_CAR_MANUFACTURERS = {"harley-davidson"}                 # xe máy
COMMERCIAL_MODEL_WORDS = ["freightliner", "international", "peterbilt", "kenworth", "hino",
                          "mack", "workhorse", "isuzu npr", "school bus"]   # xe tải/xe buýt thương mại
NON_CAR_TYPES = {"bus"}

RANDOM_STATE = 42
