# 🚗 AutoWiseAI — Tài Liệu Mô Tả Dữ Liệu & Hệ Thống Hình Ảnh

Tài liệu này cung cấp mô tả toàn diện về tập dữ liệu định giá xe ô tô cũ và hệ thống hình ảnh xe được xây dựng trong dự án **AutoWiseAI**.

---

## 📌 Mục Lục
1. [Tổng Quan Dự Án](#1-tổng-quan-dự-án)
2. [Cấu Trúc Thư Mục](#2-cấu-trúc-thư-mục)
3. [Từ Điển Dữ Liệu Bảng (Data Dictionary)](#3-từ-điển-dữ-liệu-bảng-data-dictionary)
   - [3.1 Nhóm Định Danh & Địa Lý](#31-nhóm-định-danh--địa-lý)
   - [3.2 Nhóm Thông Số Kỹ Thuật Xe](#32-nhóm-thông-số-kỹ-thuật-xe)
   - [3.3 Nhóm Đặc Trưng Kỹ Nghệ (Engineered Features)](#33-nhóm-đặc-trưng-kỹ-nghệ-engineered-features)
   - [3.4 Nhóm Từ Khóa Tùy Chọn Xe (Option Keywords)](#34-nhóm-từ-khóa-tùy-chọn-xe-option-keywords)
4. [Hệ Thống Dữ Liệu Hình Ảnh (Image System)](#4-hệ-thống-dữ-liệu-hình-ảnh-image-system)
   - [4.1 Cấu Trúc Bảng Image Manifest](#41-cấu-trúc-bảng-image-manifest)
   - [4.2 Quy Trình Thu Thập & Chuẩn Hóa Ảnh](#42-quy-trình-thu-thập--chuẩn-hóa-ảnh)
   - [4.3 Bảng Tổng Hợp Xe Kèm Ảnh (`vehicles_with_images.csv`)](#43-bảng-tổng-hợp-xe-kèm-ảnh-vehicles_with_imagescsv)
5. [Thống Kê Tổng Quan Bộ Dữ Liệu](#5-thống-kê-tổng-quan-bộ-dữ-liệu)
6. [Bản Quyền & Ghi Công Tác Giả (Licensing & Attribution)](#6-bản-quyền--ghi-công-tác-giả-licensing--attribution)
7. [Hướng Dẫn Sử Dụng Trong Python](#7-hướng-dẫn-sử-dụng-trong-python)

---

## 1. Tổng Quan Dự Án

* **Tên dự án:** AutoWiseAI — Hệ thống Định giá & Đề xuất Xe Thông Minh
* **Quy mô dữ liệu bảng:** **198,436** bản ghi xe với **48** cột thuộc tính đã được làm sạch và kỹ nghệ đặc trưng.
* **Quy mô tập hình ảnh:** Hơn **5,000+** hình ảnh chất lượng cao (~1.3 GB), độ phủ đạt xấp xỉ **90%** toàn bộ các mẫu xe trong dataset thông qua kỹ thuật gom nhóm `model_base` và sắp xếp theo độ phổ biến.
* **Mục đích sử dụng:**
  - Huấn luyện các mô hình học máy (XGBoost, LightGBM, CatBoost, Random Forest) để dự đoán giá trị thị trường của xe cũ (`price`).
  - Tích hợp mô hình học sâu đa phương thức (Multimodal Deep Learning: kết hợp đặc trưng dạng bảng và hình ảnh xe qua ResNet, EfficientNet hoặc CLIP).
  - Phục vụ ứng dụng web / giao diện tra cứu xe thông minh kèm ảnh minh họa trực quan.

---

## 2. Cấu Trúc Thư Mục

```text
AutoWiseAI/
├── assets/
│   └── car_images/                  # Chứa toàn bộ tệp ảnh xe (.jpg) đã chuẩn hóa
│       ├── ford_f150_2013.jpg
│       ├── toyota_camry_2018.jpg
│       ├── honda_civic_2015.jpg
│       └── ... (~5,000+ files, 1.3+ GB)
├── data/
│   ├── vehicles_clean.csv           # Bộ dữ liệu gốc đã tiền xử lý sạch (198,436 dòng x 48 cột)
│   ├── image_manifest.csv           # Danh mục quản lý metadata & bản quyền hình ảnh
│   └── vehicles_with_images.csv     # Bảng dữ liệu đã ghép nối đầy đủ thông tin bảng & ảnh
├── scripts/
│   └── download_car_images.py       # Script tải và chuẩn hóa ảnh tự động từ Wikimedia Commons
├── DATA_DESCRIPTION.md              # Tài liệu mô tả dữ liệu & hình ảnh (file này)
└── README.md                        # Hướng dẫn tổng quan dự án
```

---

## 3. Từ Điển Dữ Liệu Bảng (Data Dictionary)

Tập dữ liệu gốc [vehicles_clean.csv](file:///d:/AutoWiseAI/data/vehicles_clean.csv) gồm **198,436 dòng** và **48 cột**, được phân thành 4 nhóm chức năng:

### 3.1 Nhóm Định Danh & Địa Lý

| Tên Cột | Kiểu Dữ Liệu | Giá Trị Mẫu | Mô Tả |
| :--- | :--- | :--- | :--- |
| `id` | `int64` | `7301583321` | Mã định danh duy nhất của bài đăng xe trên Craigslist. |
| `region` | `string` | `hudson valley` | Khu vực/vùng đô thị nơi xe được rao bán. |
| `state` | `string` | `ny` | Mã bang tại Hoa Kỳ (viết tắt 2 chữ cái: ca, tx, ny, fl,...). |
| `lat` | `float64` | `42.598179` | Vĩ độ địa lý của vị trí xe rao bán. |
| `long` | `float64` | `-73.708295` | Kinh độ địa lý của vị trí xe rao bán. |
| `posting_date` | `string` | `2021-04-04 07:00:25+00:00` | Ngày và giờ đăng tin bán xe. |
| `posting_dow` | `int64` | `6` | Thứ trong tuần đăng tin (0 = Thứ hai, ..., 6 = Chủ nhật). |
| `seller_type` | `string` | `dealer` | Loại người bán: `dealer` (đại lý/salon xe) hoặc `owner` (chính chủ bán). |

---

### 3.2 Nhóm Thông Số Kỹ Thuật Xe

| Tên Cột | Kiểu Dữ Liệu | Giá Trị Mẫu | Mô Tả |
| :--- | :--- | :--- | :--- |
| `price` | `int64` | `18997` | **Biến mục tiêu (Target)**: Giá bán xe niêm yết (USD), từ $1,000 đến $149,998. |
| `year` | `float64` | `2013.0` | Năm sản xuất của xe (phạm vi từ 1990 đến 2022). |
| `manufacturer` | `string` | `dodge` | Hãng sản xuất xe (ford, chevrolet, toyota, honda, bmw,...). |
| `model` | `string` | `durango` | Tên model cụ thể trong tin đăng (có thể chứa trim như `civic lx`, `f-150 xlt`). |
| `model_base` | `string` | `durango` | Tên dòng xe cơ sở đã làm sạch và chuẩn hóa (dùng để gom nhóm). |
| `make_model` | `string` | `dodge durango` | Chuỗi kết hợp hãng xe và dòng xe cơ sở. |
| `manufacturer_inferred`| `int64` | `0` | Cờ đánh dấu: 1 = Hãng xe được suy luận từ tiêu đề/mô tả; 0 = Hãng xe có sẵn. |
| `condition` | `string` | `excellent` | Tình trạng xe: `excellent`, `good`, `like new`, `fair`, `salvage`, `new`. |
| `condition_rank` | `float64`| `3.0` | Điểm thứ bậc số hóa của tình trạng xe (1 = salvage đến 5 = new). |
| `cylinders` | `string` | `6 cylinders` | Số lượng xi-lanh động cơ dạng chữ (`4 cylinders`, `6 cylinders`, `8 cylinders`,...). |
| `cylinders_num` | `float64`| `6.0` | Số lượng xi-lanh động cơ dạng số nguyên. |
| `fuel` | `string` | `gas` | Loại nhiên liệu: `gas` (xăng), `diesel` (dầu), `hybrid`, `electric` (điện), `other`. |
| `odometer` | `float64`| `96475.0` | Quãng đường xe đã đi (tính bằng dặm - miles). |
| `title_status` | `string` | `clean` | Tình trạng pháp lý giấy tờ xe: `clean` (sạch), `rebuilt`, `salvage`, `lien`,... |
| `transmission` | `string` | `automatic` | Hộp số xe: `automatic` (tự động), `manual` (số sàn), `other`. |
| `drive` | `string` | `4wd` | Hệ dẫn động bánh xe: `4wd` (4 bánh), `fwd` (cầu trước), `rwd` (cầu sau). |
| `type` | `string` | `suv` | Kiểu dáng phân khúc xe: `sedan`, `suv`, `truck`, `pickup`, `coupe`, `hatchback`,... |
| `paint_color` | `string` | `black` | Màu sơn ngoại thất xe: `white`, `black`, `silver`, `blue`, `red`, `grey`,... |
| `has_vin` | `int64` | `0` | Cờ nhị phân: 1 = Bài đăng có cung cấp số khung VIN; 0 = Không có. |

---

### 3.3 Nhóm Đặc Trưng Kỹ Nghệ (Engineered Features)

| Tên Cột | Kiểu Dữ Liệu | Giá Trị Mẫu | Mô Tả & Công Thức Tính |
| :--- | :--- | :--- | :--- |
| `car_age` | `float64` | `8.0` | Tuổi của xe tại thời điểm thu thập dữ liệu (`2021 - year`). |
| `miles_per_year`| `float64` | `12059.375` | Số dặm trung bình xe chạy mỗi năm (`odometer / max(car_age, 0.5)`). |
| `log_price` | `float64` | `9.852` | Logarithm tự nhiên của giá bán: $\ln(\text{price})$. Thường dùng làm biến mục tiêu hồi quy. |
| `log_odometer` | `float64` | `11.477` | Logarithm tự nhiên của số dặm: $\ln(\text{odometer} + 1)$. Giúp giảm lệch phân phối. |
| `brand_tier` | `string` | `mainstream` | Phân cấp định vị thương hiệu: `luxury` (xe sang), `mainstream` (phổ thông), `budget` (bình dân). |
| `n_unknown_specs`| `int64` | `1` | Số lượng thông số kỹ thuật bị thiếu (`unknown`/`NaN`) trong bài đăng gốc. |
| `desc_missing` | `int64` | `0` | Cờ nhị phân: 1 = Bài đăng không có phần văn bản mô tả; 0 = Có mô tả. |
| `desc_len` | `int64` | `4744` | Tổng số ký tự trong đoạn văn bản mô tả của người bán. |
| `desc_words` | `int64` | `705` | Tổng số lượng từ trong đoạn văn bản mô tả. |

---

### 3.4 Nhóm Từ Khóa Tùy Chọn Xe (Option Keywords)

Các cờ nhị phân (`1` = Có đề cập, `0` = Không đề cập) được trích xuất tự động qua xử lý ngôn ngữ tự nhiên từ phần mô tả bài đăng:

| Tên Cột | Ý Nghĩa Từ Khóa | Tác Động Đến Giá Xe |
| :--- | :--- | :--- |
| `kw_one_owner` | Xe 1 đời chủ duy nhất (*One Owner*) | Thường giữ giá tốt hơn (+). |
| `kw_clean_history` | Lịch sử trong sạch, không tai nạn (*Clean Carfax / History*) | Tăng độ tin cậy và giá xe (+). |
| `kw_warranty` | Còn bảo hành hãng hoặc bảo hành đại lý (*Warranty*) | Tăng giá trị (+). |
| `kw_financing` | Đại lý hỗ trợ vay trả góp (*Financing Available*) | Thường gặp ở xe salon (+). |
| `kw_needs_work` | Xe có lỗi, cần sửa chữa/bảo dưỡng (*Needs Work / TLC*) | Giảm giá xe mạnh (-). |
| `kw_new_tires` | Lốp xe mới thay gần đây (*New Tires*) | Điểm cộng trang bị (+). |
| `kw_leather` | Xe trang bị nội thất ghế da (*Leather Seats*) | Tùy chọn cao cấp (+). |
| `kw_sunroof` | Có cửa sổ trời / mui kính panorama (*Sunroof / Moonroof*) | Tùy chọn cao cấp (+). |
| `kw_navigation` | Có hệ thống định vị GPS dẫn đường (*Navigation / GPS*) | Tùy chọn tiện ích (+). |
| `kw_backup_camera`| Có camera lùi (*Backup Camera / Rearview Camera*) | Tiện ích an toàn (+). |
| `kw_lifted` | Xe độ nâng gầm địa hình (*Lifted / Suspension Lift*) | Đặc trưng cho dòng bán tải/SUV. |
| `kw_low_miles` | Xe chạy ít dặm so với đời xe (*Low Mileage*) | Tăng giá xe (+). |

---

## 4. Hệ Thống Dữ Liệu Hình Ảnh (Image System)

### 4.1 Cấu Trúc Bảng Image Manifest

File [image_manifest.csv](file:///d:/AutoWiseAI/data/image_manifest.csv) đóng vai trò là "sổ đăng ký" quản lý toàn bộ hình ảnh xe, liên kết giữa dữ liệu bảng và tệp ảnh thực tế trên đĩa:

| Tên Cột | Kiểu Dữ Liệu | Giá Trị Mẫu | Mô Tả |
| :--- | :--- | :--- | :--- |
| `image_key` | `string` | `ford_f150_2013` | Khóa định danh chuẩn hóa: `{hãng}_{dòng xe cơ sở}_{năm}`. |
| `image_path` | `string` | `assets/car_images/ford_f150_2013.jpg` | Đường dẫn tương đối từ gốc dự án đến tệp ảnh JPEG. |
| `image_source` | `string` | `https://commons.wikimedia.org/wiki/File:...` | URL bài viết gốc chứa ảnh trên Wikimedia Commons. |
| `image_license` | `string` | `CC BY-SA 4.0` | Loại giấy phép bản quyền mở hợp pháp của bức ảnh. |
| `image_license_url` | `string` | `https://creativecommons.org/licenses/by-sa/4.0` | Link chính thức đến điều khoản cấp phép Creative Commons. |
| `image_artist` | `string` | `Vauxford` | Tên tác giả / nhiếp ảnh gia chụp và cấp phép ảnh. |
| `image_match_score` | `float64`| `12.0` | Điểm số độ khớp của ảnh với từ khóa xe (ngưỡng chấp nhận $\ge 8.0$). |
| `image_status` | `string` | `downloaded` | Trạng thái: `downloaded` (đã tải thành công) hoặc `not_found` (không tìm thấy ảnh đạt chuẩn). |

---

### 4.2 Quy Trình Thu Thập & Chuẩn Hóa Ảnh

Script [download_car_images.py](file:///d:/AutoWiseAI/scripts/download_car_images.py) tự động thực thi các bước:

1. **Gom nhóm thông minh & Sắp xếp theo độ phổ biến:**
   - Sử dụng `model_base` thay vì model chi tiết, giảm số lượng truy vấn từ 48,238 xuống còn 10,692 mẫu độc nhất.
   - Các dòng xe xuất hiện nhiều nhất trong bài đăng (Ford F-150, Chevrolet Silverado, Toyota Camry,...) được ưu tiên tải trước.
2. **Tìm kiếm qua Wikimedia Commons API:**
   - Xây dựng chuỗi truy vấn đa cấp: `"{brand} {model} {year} automobile"` $\rightarrow$ `"{brand} {model} {year}"` $\rightarrow$ `"{brand} {model} automobile"`.
   - Độ trễ 1.0 giây giữa các lượt gọi API tuân thủ chính sách tôn trọng máy chủ Wikimedia.
3. **Thuật toán chấm điểm ảnh (`image_score`):**
   - **+3 điểm**: Tiêu đề ảnh chứa tên hãng xe (chuẩn hóa không phân biệt ký tự đặc biệt).
   - **+5 điểm**: Tiêu đề ảnh chứa tên dòng xe (ví dụ: `f150` khớp với `Ford F-150`).
   - **+2 điểm**: Tiêu đề ảnh chứa chính xác năm sản xuất của đời xe.
   - **+1 điểm**: Chiều rộng $\ge 400\text{ px}$.
   - **+1 điểm**: Chiều cao $\ge 250\text{ px}$.
   - **-10 điểm**: Loại trừ ảnh không phải ngoại thất xe (chứa từ khóa: `logo`, `badge`, `diagram`, `engine`, `interior`, `wheel`, `dashboard`, `emblem`).
4. **Chuẩn hóa ảnh lưu trữ:**
   - Chuyển đổi toàn bộ sang không gian màu **RGB** và định dạng **JPEG**.
   - Resize tỷ lệ chuẩn với kích thước tối đa **1200 x 900 pixel** bằng thuật toán lấy mẫu cao cấp `LANCZOS`.
   - Nén chất lượng **Quality = 90%** giúp tối ưu kích thước file mà vẫn giữ nguyên độ sắc nét cho mô hình Vision.

---

### 4.3 Bảng Tổng Hợp Xe Kèm Ảnh (`vehicles_with_images.csv`)

Bảng [vehicles_with_images.csv](file:///d:/AutoWiseAI/data/vehicles_with_images.csv) là kết quả ghép (left merge) giữa bảng xe gốc [vehicles_clean.csv](file:///d:/AutoWiseAI/data/vehicles_clean.csv) và bảng [image_manifest.csv](file:///d:/AutoWiseAI/data/image_manifest.csv) thông qua khóa chung `_image_key`.

* Cung cấp dữ liệu dạng bảng hoàn chỉnh kèm 7 cột hình ảnh: `image_path`, `image_source`, `image_license`, `image_license_url`, `image_artist`, `image_match_score`, `image_status`.
* Mỗi dòng xe có thể trích xuất trực tiếp đường dẫn file ảnh để đưa vào DataLoader của PyTorch / TensorFlow.

---

## 5. Thống Kê Tổng Quan Bộ Dữ Liệu

### 5.1 Các Chỉ Số Số Học Quan Trọng

| Chỉ Số | Giá Bán (`price`, $) | Số Dặm (`odometer`, miles) | Năm Sản Xuất (`year`) | Tuổi Xe (`car_age`, năm) |
| :--- | :--- | :--- | :--- | :--- |
| **Giá trị nhỏ nhất (Min)** | 1,000 | 0 | 1990 | 0 |
| **Trung vị (Median)** | 11,998 | 104,352 | 2012 | 9 |
| **Giá trị lớn nhất (Max)** | 149,998 | 400,000 | 2022 | 31 |

### 5.2 Top 10 Thương Hiệu Xe Chiếm Thị Phần Lớn Nhất

1. **Ford**: 33,673 xe (17.0%)
2. **Chevrolet**: 25,368 xe (12.8%)
3. **Toyota**: 18,157 xe (9.1%)
4. **Honda**: 12,796 xe (6.4%)
5. **Nissan**: 10,479 xe (5.3%)
6. **Jeep**: 9,259 xe (4.7%)
7. **GMC**: 7,363 xe (3.7%)
8. **RAM**: 6,929 xe (3.5%)
9. **BMW**: 6,666 xe (3.4%)
10. **Dodge**: 6,313 xe (3.2%)

### 5.3 Thống Kê Độ Phủ Hình Ảnh

* **Tổng số ảnh đã tải về đĩa:** > 5,040 tệp ảnh (~1.32 GB).
* **Tỷ lệ bài đăng có ảnh minh họa:** **178,062 / 198,436 xe (~89.7%)**.
* **Tỷ lệ không tìm thấy ảnh phù hợp (`not_found`):** ~6.4% (chủ yếu là các dòng xe siêu hiếm hoặc các đời xe quá cũ trước năm 1995).

---

## 6. Bản Quyền & Ghi Công Tác Giả (Licensing & Attribution)

Hệ thống hình ảnh tuân thủ nghiêm ngặt các quy định pháp lý và đạo đức dữ liệu:
* Toàn bộ ảnh được lưu trữ cùng thông tin tác giả (`image_artist`), link nguồn gốc (`image_source`) và đường dẫn cấp phép (`image_license_url`).
* Phân bố các loại giấy phép của kho ảnh:
  - **CC BY-SA 4.0** (~45%): Giấy phép ghi công & chia sẻ tương tự quốc tế.
  - **Public domain** (~23%): Thuộc phạm vi công cộng, không yêu cầu bản quyền.
  - **CC BY 2.0** (~11%): Giấy phép tự do ghi công tác giả.
  - **CC BY-SA 3.0** (~7%): Chia sẻ tương tự phiên bản 3.0.
  - **CC0** (~6%): Tác giả từ bỏ bản quyền hoàn toàn cho cộng đồng.

---

## 7. Hướng Dẫn Sử Dụng Trong Python

### 7.1 Đọc Dữ Liệu Bảng Kèm Ảnh Bằng Pandas

```python
import pandas as pd
from pathlib import Path
from PIL import Image

BASE_DIR = Path(".")

# 1. Nạp bảng dữ liệu đã kèm đường dẫn ảnh
df = pd.read_csv(BASE_DIR / "data" / "vehicles_with_images.csv")

# 2. Lọc các dòng xe đã có ảnh tải về
df_with_img = df[df["image_status"] == "downloaded"].copy()
print(f"Số lượng xe có ảnh hợp lệ: {len(df_with_img):,} xe")

# 3. Mở và xem ảnh của một dòng bất kỳ
sample_row = df_with_img.iloc[0]
image_path = BASE_DIR / sample_row["image_path"]

print(f"Xe: {sample_row['year']:.0f} {sample_row['manufacturer'].upper()} {sample_row['model']}")
print(f"Giá bán: ${sample_row['price']:,}")
print(f"Ảnh tại: {image_path}")

img = Image.open(image_path)
img.show()
```

### 7.2 Xây Dựng Dataset Đa Phương Thức (PyTorch Example)

```python
import torch
from torch.utils.data import Dataset
from PIL import Image
from pathlib import Path

class CarMultimodalDataset(Dataset):
    def __init__(self, df, base_dir, transform=None):
        self.df = df[df["image_status"] == "downloaded"].reset_index(drop=True)
        self.base_dir = Path(base_dir)
        self.transform = transform
        
        # Các cột dạng bảng làm đặc trưng
        self.feature_cols = [
            "car_age", "miles_per_year", "log_odometer",
            "condition_rank", "cylinders_num", "kw_leather", "kw_sunroof"
        ]

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        
        # 1. Nạp ảnh
        img_path = self.base_dir / row["image_path"]
        image = Image.open(img_path).convert("RGB")
        if self.transform:
            image = self.transform(image)
            
        # 2. Vector đặc trưng dạng bảng
        tabular_feats = torch.tensor(row[self.feature_cols].values.astype(float), dtype=torch.float32)
        
        # 3. Nhãn giá xe
        target_price = torch.tensor(row["log_price"], dtype=torch.float32)
        
        return image, tabular_feats, target_price
```
