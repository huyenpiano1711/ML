# AutoWise AI

Ứng dụng học máy dự đoán giá xe ô tô đã qua sử dụng và đề xuất xe phù hợp với nhu cầu người dùng.
Môn Học máy trong Phân tích Kinh doanh.

- **Dữ liệu:** Craigslist Cars & Trucks (Kaggle), 426.880 tin đăng tại Mỹ, 04–05/2021. Giá tính bằng USD, quãng đường tính bằng dặm.
- **Đã xong:** EDA, tiền xử lý dữ liệu (15 bước lọc; lọc ngoại lai theo nhóm xe chuyển sang sau bước chia tập), giải mã VIN, điền dữ liệu thiếu, thu thập và khử trùng ảnh minh họa, mô hình dự đoán giá (HistGradientBoosting), gợi ý xe (KNN), backend và ứng dụng desktop PyQt6.

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

Ngoài các thư mục trên:

| Thư mục | Nội dung |
|---|---|
| `src/prediction/`, `models/price_prediction/` | Huấn luyện và mô hình giá `final_pipeline.joblib` |
| `src/recommendation/` | Danh mục xe gợi ý (`build_catalog.py`) và KNN (`recommend.py`) |
| `backend/` | `app_service.analyze()`: kiểm tra dữ liệu nhập, dự đoán giá, Top 5, xe cùng tầm giá, ảnh |
| `desktop_app/` | Ứng dụng PyQt6: `UI/` (file `.ui`, file sinh bằng pyuic6, file `*Ex.py`), `controllers/`, `widgets/`, `dal/` (tài khoản SQLite) |
| `tests/` | Test tự động (`python -m pytest -q`) |

## Cài đặt

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Luôn chạy ứng dụng và test bằng Python trong `.venv` của dự án. Mô hình `final_pipeline.joblib` được lưu bằng scikit-learn 1.9.1, numpy 2 và pandas 3, nên Python khác (thiếu thư viện hoặc sai phiên bản) không nạp được mô hình. Phiên bản tối thiểu: `scikit-learn==1.9.1`, `numpy>=2.0`, `pandas>=2.3` (đã ghi trong `requirements.txt`).

PyCharm: **Settings → Project → Python Interpreter → Add Interpreter → Existing**, chọn `.venv\Scripts\python.exe` trong thư mục dự án. Kiểm tra nhanh:

```bash
.venv\Scripts\python -c "import sklearn, numpy, pandas; print(sklearn.__version__, numpy.__version__, pandas.__version__)"
.venv\Scripts\python -m pytest -q
```

Mở ứng dụng: `.venv\Scripts\python main.py`. Ứng dụng luôn bắt đầu ở màn hình đăng nhập; chưa đăng nhập thì không dùng được chức năng nào.

| Vai trò | Màn hình sau khi đăng nhập | Chức năng |
|---|---|---|
| Người dùng (`user`) | Cửa sổ AutoWise | Nhập thông tin xe → giá ước tính, khoảng giá 80%, Top 5 gợi ý, xe cùng tầm giá; lưu xe yêu thích, so sánh 2–3 xe, lịch sử tra cứu, xuất PDF, hồ sơ và đổi mật khẩu |
| Quản trị (`admin`) | Cửa sổ AutoWise Admin | Dashboard thống kê, quản lý người dùng (khóa/mở khóa, đổi vai trò, đặt lại mật khẩu, xóa), quản lý mô hình (huấn luyện, lưu phiên bản, kích hoạt), khám phá dữ liệu và phân cụm KMeans, nhật ký hoạt động |

Tài khoản quản trị mặc định được tạo ở lần chạy đầu: `admin` / `Admin@2026`. Hãy đổi mật khẩu sau lần đăng nhập đầu tiên.

Nếu mở ứng dụng bằng Python sai phiên bản, cửa sổ chính báo ngay lúc khởi động (hộp thoại "AutoWise could not load everything"), ghi rõ thư viện nào sai và cần bản nào.

### Ràng buộc dữ liệu nhập trên giao diện

| Ô nhập | Ràng buộc |
|---|---|
| Họ tên (khi đăng ký) | 1–60 ký tự, phải có chữ cái; chỉ gồm chữ (kể cả tiếng Việt), khoảng trắng và `. ' -`; luôn hiển thị dạng chữ thường (không hiểu thành HTML) |
| Tên đăng nhập | 3–30 ký tự: chữ, số, `_`, `.` |
| Email | Không bắt buộc; tối đa 100 ký tự; mỗi email chỉ dùng cho một tài khoản |
| Mật khẩu | 8–64 ký tự, có cả chữ và số |
| Mật khẩu (bổ sung) | Không chứa khoảng trắng, không chứa tên đăng nhập |
| Đăng nhập | Sai 3 lần trong một lần mở app thì app tự đóng; tài khoản sai 3 lần liên tiếp bị khóa 5 phút (lưu trong CSDL); tài khoản bị khóa bởi quản trị không đăng nhập được |
| Hãng, dòng xe | Bắt buộc; gõ một phần tên (gợi ý hiện ra) hoặc lướt danh sách để chọn; tên không có trong danh sách thì không được nhận |
| Kiểu dáng, tình trạng, nhiên liệu, hộp số | Không bắt buộc; để "Not sure" thì mô hình nhận `unknown` |
| Tùy chọn nâng cao | Luôn hiện, không bắt buộc; chỉ còn tình trạng giấy tờ và bang; đã bỏ hệ dẫn động, số xi-lanh, màu xe (dữ liệu thiếu 27–35%) |
| Số dặm | Không quá 50.000 dặm cho mỗi năm tuổi xe (tuổi xe = 2021 − năm, tối thiểu 1); xe tình trạng "New" tối đa 10.000 dặm |

Giá ước tính dựa trên tin rao tại Mỹ năm 2021, không phải giá thị trường hiện tại; trang kết quả có ghi chú điều này.

## Tải dữ liệu

Dữ liệu và ảnh quá lớn cho git nên được đính kèm ở mục **Releases** của repo (bản `data-v1`). Giải nén tại **thư mục gốc repo**; riêng ba file ảnh giải nén vào thư mục `assets/`.

| File | Dung lượng | Giải nén vào | Nội dung |
|---|---|---|---|
| `autowise_data_processed.zip` | 61 MB | thư mục gốc | `data/processed/`: dữ liệu sạch và dữ liệu đã điền |
| `autowise_data_interim.zip` | 10 MB | thư mục gốc | `data/interim/`: đặc trưng mô tả, kết quả giải mã VIN |
| `vehicles_raw.zip` | 273 MB | thư mục gốc | `data/raw/vehicles.csv` (chỉ cần khi chạy lại từ đầu) |
| `car_images_unique_part1..3.zip` | 720 + 687 + 514 MB | `assets/` | `car_images_unique/` (6.842 ảnh) |

Kiểm tra file tải về bằng `SHA256SUMS.txt` (Windows: `certutil -hashfile <file> SHA256`).

**Phần lớn thành viên chỉ cần `autowise_data_processed.zip`.** Dữ liệu dùng cho mô hình là `data/processed/vehicles_filled.pkl` (201.434 dòng); chi tiết ở [docs/data_handoff.md](docs/data_handoff.md).

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
| `03_preprocess.py` | Làm sạch 15 bước, tạo đặc trưng | `data/processed/vehicles_clean.*`, `reports/cleaning_log.csv` |
| `04_eda_clean.py` | EDA dữ liệu sạch | `reports/eda_clean/` |
| `05_validate.py` | 29 kiểm tra tự động và mô hình cơ sở | in ra màn hình |
| `06_prepare_vin_list.py`, `07_vin_decode.py` | Giải mã VIN qua API NHTSA (cần internet, khoảng 1 giờ) | `data/interim/vin_decoded.csv` |
| `08_fill_specs.py` | Điền 5 cột thông số bằng VIN và nhóm xe | `data/processed/vehicles_filled.*` |
| `09_fill_experiment.py` | So sánh mô hình trước và sau khi điền | `reports/fill_experiment.csv` |
| `10_image_audit.py` | Kiểm toán bộ ảnh (SHA-256, pHash) | `reports/image_audit/` |
| `11_report_tables.py` | Bảng số liệu bổ sung cho báo cáo | `reports/*.csv` |
| `12_split_data.py` | Chia train/val/test 70/15/15 theo nhóm xe (StratifiedGroupKFold, không để cùng một xe nằm ở hai tập); học ngưỡng ngoại lai trên train và chỉ loại khỏi train | `data/splits/*_ids.csv`, `reports/split_summary.csv`, `reports/removed_group_outliers.csv` |
| `13_build_feature_schema.py` | A04: thuộc tính đầu vào, khớp với form PyQt6 | `src/features/feature_schema.json` |
| `14_feature_check.py` | A04: kiểm chứng bộ thuộc tính trên tập validation | `reports/feature_selection.csv` |
| `19_train_final_model.py` | So sánh thuật toán, tinh chỉnh, huấn luyện mô hình cuối, đánh giá test một lần, khoảng giá 80% | `models/price_prediction/`, `reports/prediction/` |
| `20_cross_validation.py` | Kiểm định chéo 5 lần theo nhóm | `reports/prediction/cross_validation.csv` |
| `16_backend_performance.py` | Đo thời gian phản hồi của backend | `reports/integration/` |
| `21_app_screenshots.py` | Chụp màn hình ứng dụng (CSDL tạm) cho báo cáo | `docs/screenshots/` |

`run_all.py` chạy 01–05. Hai file `.bat` là lối tắt chạy bước 07 và kiểm tra kết nối trên Windows.

## Quy ước cho giai đoạn huấn luyện

- Biến mục tiêu: `log_price`; dự đoán xong đổi ngược bằng `np.expm1`.
- Dùng chung cách chia trong `data/splits/` (đọc `id` rồi lọc `vehicles_filled.pkl`), không tự chia lại. Fit `build_preprocessor()` và `GroupModeImputer` **chỉ trên train**; chọn mô hình trên **val**; **test** chỉ dùng một lần ở `19_train_final_model.py`.
- Cột đầu vào của mô hình giá: `price_model_columns` trong `src/features/feature_schema.json` (17 cột, chỉ gồm thông tin người dùng nhập trên form hoặc tính được). Chi tiết: [docs/A03_A04_split_and_features.md](docs/A03_A04_split_and_features.md).
- Kết quả mô hình cuối (HistGradientBoosting, `models/price_prediction/metrics.json`): trên tập test, MAE 2.498 USD khi đủ thông tin và 2.639 USD theo đúng cách ứng dụng gửi dữ liệu (để trống hệ dẫn động, số xi-lanh, màu xe); khoảng giá 80% phủ 79,9% số xe test. Con số 2.094 USD trong `fill_experiment.csv` dùng cả cột mô tả, VIN, tọa độ và chia 80/20 nên không so trực tiếp được.
- Không commit dữ liệu, ảnh hay file lớn hơn 100 MB; cập nhật dữ liệu bằng Release mới.
