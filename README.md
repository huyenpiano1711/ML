# AutoWise AI

Ứng dụng học máy dự đoán giá xe ô tô đã qua sử dụng và đề xuất xe phù hợp với nhu cầu người dùng.
Môn Học máy trong Phân tích Kinh doanh.

- **Dữ liệu:** Craigslist Cars & Trucks (Kaggle), 426.880 tin đăng tại Mỹ, 04–05/2021. Giá tính bằng USD, quãng đường tính bằng dặm.
- **Đã xong:** EDA, tiền xử lý dữ liệu (16 bước lọc), giải mã VIN, điền dữ liệu thiếu, thu thập và khử trùng ảnh minh họa.
- **Tiếp theo:** dự đoán giá, gợi ý xe, backend và giao diện PyQt6 (theo ML Draft của nhóm).

## Cấu trúc thư mục

```
AutoWise/
├── README.md
├── requirements.txt
├── data/                      # không đưa lên git, tải từ Release (xem bên dưới)
│   ├── raw/vehicles.csv
│   ├── interim/               # desc_features.csv, vin_decoded.csv, vins_to_decode.csv
│   └── processed/             # vehicles_clean.pkl/.csv, vehicles_filled.pkl/.csv
├── assets/
│   ├── car_images_unique/     # 6.842 ảnh minh họa, tải từ Release
│   └── car_images/            # bộ ảnh crawl gốc 8.709 file (chỉ cần khi chạy lại 10_image_audit.py)
├── scripts/                   # EDA và tiền xử lý đã thực hiện
│   ├── 01_eda_raw.py … 11_report_tables.py
│   ├── run_all.py             # chạy 01–05
│   ├── download_car_images.py, deduplicate_car_images.py,
│   │   consolidate_exact_duplicates.py, delete_exact_duplicates.py
│   └── README_image_deduplication.md
├── src/
│   ├── config.py              # đường dẫn và ngưỡng làm sạch
│   ├── cleaning.py, data_loader.py, plot_utils.py, vin_mapping.py
│   └── features/
│       └── preprocessing.py   # add_features, GroupModeImputer, build_preprocessor
├── reports/                   # biểu đồ và bảng kết quả EDA
│   ├── eda_raw/, eda_clean/, image_audit/
│   └── cleaning_log.csv, data_dictionary.csv, fill_experiment.csv, …
└── docs/
    ├── data_handoff.md        # mô tả bộ dữ liệu bàn giao
    └── DATA_DESCRIPTION.md    # mô tả bộ ảnh và bảng ảnh
```

Các thư mục `models/`, `backend/`, `desktop_app/`, `tests/`, `src/prediction/`, `src/recommendation/` sẽ được thêm khi các phần việc tương ứng hoàn thành, theo cấu trúc trong ML Draft.

## Cài đặt

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

## Tải dữ liệu

Dữ liệu và ảnh quá lớn cho git nên được đính kèm ở mục **Releases** của repo (bản `data-v1`). Giải nén tại **thư mục gốc repo**; riêng ba file ảnh giải nén vào thư mục `assets/`.

| File | Dung lượng | Giải nén vào | Nội dung |
|---|---|---|---|
| `autowise_data_processed.zip` | 61 MB | thư mục gốc | `data/processed/`: dữ liệu sạch và dữ liệu đã điền |
| `autowise_data_interim.zip` | 10 MB | thư mục gốc | `data/interim/`: đặc trưng mô tả, kết quả giải mã VIN |
| `vehicles_raw.zip` | 273 MB | thư mục gốc | `data/raw/vehicles.csv` (chỉ cần khi chạy lại từ đầu) |
| `car_images_unique_part1..3.zip` | 720 + 687 + 514 MB | `assets/` | `car_images_unique/` (6.842 ảnh) |

Kiểm tra file tải về bằng `SHA256SUMS.txt` (Windows: `certutil -hashfile <file> SHA256`).

**Phần lớn thành viên chỉ cần `autowise_data_processed.zip`.** Dữ liệu dùng cho mô hình là `data/processed/vehicles_filled.pkl` (198.514 dòng × 65 cột); chi tiết ở [docs/data_handoff.md](docs/data_handoff.md).

```python
import pandas as pd
df = pd.read_pickle("data/processed/vehicles_filled.pkl")
```

## Chạy lại quy trình

Chạy từ thư mục `scripts/` theo thứ tự số (PyCharm: chuột phải → Run).

| Script | Việc làm | Đầu ra |
|---|---|---|
| `01_eda_raw.py` | EDA dữ liệu gốc | `reports/eda_raw/` |
| `02_extract_text_features.py` | 15 đặc trưng từ cột mô tả | `data/interim/desc_features.csv` |
| `03_preprocess.py` | Làm sạch 16 bước, tạo đặc trưng | `data/processed/vehicles_clean.*`, `reports/cleaning_log.csv` |
| `04_eda_clean.py` | EDA dữ liệu sạch | `reports/eda_clean/` |
| `05_validate.py` | 29 kiểm tra tự động và mô hình cơ sở | in ra màn hình |
| `06_prepare_vin_list.py`, `07_vin_decode.py` | Giải mã VIN qua API NHTSA (cần internet, khoảng 1 giờ) | `data/interim/vin_decoded.csv` |
| `08_fill_specs.py` | Điền 5 cột thông số bằng VIN và nhóm xe | `data/processed/vehicles_filled.*` |
| `09_fill_experiment.py` | So sánh mô hình trước và sau khi điền | `reports/fill_experiment.csv` |
| `10_image_audit.py` | Kiểm toán bộ ảnh (SHA-256, pHash) | `reports/image_audit/` |
| `11_report_tables.py` | Bảng số liệu bổ sung cho báo cáo | `reports/*.csv` |

`run_all.py` chạy 01–05. Hai file `.bat` là lối tắt chạy bước 07 và kiểm tra kết nối trên Windows.

## Quy ước cho giai đoạn huấn luyện

- Biến mục tiêu: `log_price`; dự đoán xong đổi ngược bằng `np.expm1`.
- Chia train/test **trước**, rồi mới fit `build_preprocessor()` và `GroupModeImputer` trên tập train (tránh rò rỉ dữ liệu).
- Mốc cần vượt: Ridge MAE 3.055 USD; HistGradientBoosting MAE 2.094 USD (`reports/fill_experiment.csv`).
- Không commit dữ liệu, ảnh hay file lớn hơn 100 MB; cập nhật dữ liệu bằng Release mới.
