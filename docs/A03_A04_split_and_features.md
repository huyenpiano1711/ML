# A03 – Chia tập dữ liệu · A04 – Chọn thuộc tính đầu vào

Người thực hiện: Duy · Dữ liệu: `data/processed/vehicles_filled.pkl` (201.434 × 65)

## Cách chạy lại

```
cd scripts
python 12_split_data.py            # A03 -> data/splits/, reports/split_summary.csv
python 13_build_feature_schema.py  # A04 -> src/features/feature_schema.json
python 14_feature_check.py         # A04 -> reports/feature_selection.csv (khoảng 15 giây)
```

Kết quả cố định: `random_state = 42`, chạy lại cho ra đúng các file id như cũ.

---

## A03 – Chia tập dữ liệu

| Tập | Số dòng | Tỷ lệ | Dùng cho |
|---|---|---|---|
| train | 141.828 | 70,4% | Huấn luyện; fit `GroupModeImputer`, encoder, scaler; học ngưỡng ngoại lai |
| val | 28.777 | 14,3% | So sánh mô hình, chỉnh tham số, tính khoảng giá 80% |
| test | 28.777 | 14,3% | Báo cáo kết quả cuối, **chỉ dùng một lần** |

**Cách chia.** `StratifiedGroupKFold` theo nhóm hãng + dòng + năm + số dặm, phân tầng theo khoảng giá: các tin đăng lại của cùng một xe luôn nằm chung một tập. Mỗi file chỉ lưu cột `id` nên đưa được lên git.

**Ngoại lai theo nhóm.** Trung vị và MAD của log giá theo nhóm hãng + dòng + năm chỉ học trên train (`cleaning.fit_group_outliers`). Tin có |robust z| > 3,5 chỉ bị loại khỏi train: 2.052 tin (`reports/removed_group_outliers.csv`). Val và test giữ nguyên; tin vượt ngưỡng ở hai tập này chỉ được đánh dấu trong `reports/eval_outlier_flags.csv`.

**Kiểm tra (`reports/split_summary.csv`).**

- Ba tập không trùng `id`.
- Giá trung vị: 11.997 USD (train), 11.995 USD (val, test).
- Giá trung bình: 15.946 – 16.075 USD.
- Năm trung vị đều là 2012; số dặm trung vị 104.308 – 104.625 dặm.
- Tỷ lệ tin đại lý: 68,4 – 68,5%.

**Cách dùng:**

```python
import pandas as pd
df = pd.read_pickle("data/processed/vehicles_filled.pkl")
ids = {k: pd.read_csv(f"data/splits/{k}_ids.csv")["id"] for k in ("train", "val", "test")}
train, val, test = (df[df["id"].isin(ids[k])] for k in ("train", "val", "test"))
```

**Ghi chú.** Bản đầu của dự án lọc ngoại lai theo nhóm trên toàn bộ dữ liệu trước khi chia tập (2.920 tin). Cách đó để thông tin của val/test lọt vào bước làm sạch nên đã được thay bằng cách ở trên.

---

## A04 – Chọn thuộc tính đầu vào

**Nguyên tắc.** Một cột chỉ được đưa vào mô hình nếu lúc chạy ứng dụng có được giá trị của nó, tức là người dùng nhập trên form PyQt6 hoặc hệ thống tự tính được. Nếu mô hình học một cột mà form không có, Backend sẽ không có giá trị để đưa vào lúc dự đoán.

### Đối chiếu với form (Màn hình 2)

| Ô trên form | Cột | Bắt buộc | Mô hình giá | Gợi ý | Khi bỏ trống |
|---|---|---|---|---|---|
| Hãng xe | `manufacturer` | Có | Có | Có | |
| Dòng xe | `model_base` | Có | (qua `make_model`) | Có | |
| Năm sản xuất | `year` | Có | (qua `car_age`) | Có | |
| Kiểu dáng | `type` | Không | Có | Có | `unknown` rồi `GroupModeImputer` |
| Số miles đã đi | `odometer` | Có | Có | Có | |
| Tình trạng xe | `condition` | Không | Có | Có | `unknown` (nhóm riêng mô hình đã học) |
| Nhiên liệu | `fuel` | Không | Có | Có | `unknown` rồi `GroupModeImputer` |
| Hộp số | `transmission` | Không | Có | Có | `unknown` rồi `GroupModeImputer` |
| Ngân sách tối đa | `budget_max_usd` | Có | Không | Lọc `price ≤ ngân sách` | |
| Hệ dẫn động (đã bỏ khỏi form) | `drive` | Không | Có | Có | `unknown` rồi `GroupModeImputer` |
| Số xi-lanh (đã bỏ khỏi form) | `cylinders` | Không | Có | | `unknown` rồi `GroupModeImputer` |
| Màu xe (đã bỏ khỏi form) | `paint_color` | Không | Có | | `unknown` |
| Tình trạng giấy tờ | `title_status` | Không | Có | | `clean` |
| Bang tại Mỹ | `state` | Không | Có | | `ca` |

Cập nhật 07/11/2026: bỏ ba ô Hệ dẫn động, Số xi-lanh, Màu xe khỏi form vì dữ liệu thiếu 27–35% (và màu không khớp ảnh minh họa); Backend luôn gửi `unknown` cho ba cột này. Kiểu dáng, Tình trạng, Nhiên liệu, Hộp số không còn bắt buộc. Mô hình không đổi; trên tập test, gửi `unknown` cho ba cột đã bỏ làm MAE tăng từ 2.259 lên 2.590 USD.

Hệ thống tự tính: `car_age`, `log_odometer`, `miles_per_year`, `cylinders_num`, `condition_rank`, `brand_tier`, `make_model`. Công thức giống `add_features()` trong `src/features/preprocessing.py`.

**Mô hình giá dùng 17 cột:**

- 6 cột số: `car_age`, `odometer`, `log_odometer`, `miles_per_year`, `cylinders_num`, `condition_rank`.
- 10 cột phân loại.
- `make_model`.

### Cột bị loại

- Mô tả tin đăng: `desc_*`, `kw_*`.
- VIN: `has_vin`, `vin_*`.
- Thông tin tin đăng: `seller_type`, `lat`, `long`, `region`, `posting_date`, `posting_dow`.
- `n_unknown_specs` và các cờ kỹ thuật.

Lý do từng cột ghi trong `excluded_columns` của file JSON.

### Kiểm chứng bằng số liệu (`reports/feature_selection.csv`)

Mô hình HistGradientBoosting (tham số như `09_fill_experiment.py`), học trên train, đánh giá trên val (29.777 dòng):

| Cấu hình | Số cột | MAE (USD) | MedAE (USD) | R² (log) | MAPE |
|---|---|---|---|---|---|
| Mốc: luôn đoán giá trung vị | – | 9.440 | 6.498 | 0,000 | 88,4% |
| Toàn bộ cột (gồm mô tả, tọa độ, loại người bán) | 36 | 2.179 | 1.246 | 0,914 | 17,5% |
| **Chỉ cột trên form, điền đủ** | **17** | **2.330** | **1.336** | **0,903** | **19,0%** |
| Chỉ cột trên form, bỏ trống cả 5 ô nâng cao | 17 | 2.789 | 1.589 | 0,879 | 21,7% |

Nhận xét:

- Bỏ 19 cột không nhập được trên form chỉ làm MAE tăng 151 USD (+6,9%), trong khi mô hình vẫn tốt hơn nhiều so với mốc đoán trung vị.
- Nếu người dùng bỏ trống ô nâng cao, sai số tăng nhiều nhất ở **Hệ dẫn động** (+198 USD) và **Bang** (+184 USD). Tiếp theo là xi-lanh (+119), giấy tờ (+72) và màu xe (+16).
- **Gợi ý cho E01/E02:** giao diện nên khuyến khích người dùng điền Hệ dẫn động và Bang.

**Lưu ý:** Mốc 2.094 USD trong `fill_experiment.csv` dùng cả cột mô tả, VIN và tọa độ, lại chia 80/20, nên không so trực tiếp được với các con số ở đây.

### Cấu trúc `src/features/feature_schema.json`

| Khóa | Nội dung | Người dùng |
|---|---|---|
| `price_model_columns` | Danh sách cột đưa vào mô hình giá | B02–B06 |
| `features[]` | Từng thuộc tính: nhãn trên form, widget, bắt buộc, min/max, `allowed_values` (mọi giá trị mô hình đã thấy), `ui_options` (giá trị hiển thị trên dropdown), `labels_vi`, `default`, `if_blank` | D01, E02 |
| `options.model_base_by_manufacturer` | Dòng xe theo hãng: 46 hãng, 498 dòng xe có từ 20 tin trở lên trong train | E02 |
| `recommendation_columns` | Cột lọc bắt buộc, cột tính độ tương đồng, cột hiển thị trên thẻ xe | C01–C03 |
| `excluded_columns` | Cột bị loại và lý do | Báo cáo |
| `training_notes` | Ghi chú cho người huấn luyện | B02 |

**Việc cần làm ở các task sau:**

1. **B02/B05:** pipeline lưu ra file phải gồm cả `GroupModeImputer` đã fit trên train, vì Backend cần nó để điền `drive` và `cylinders` khi người dùng bỏ trống.
2. **E02:** dropdown Dòng xe lấy từ `options.model_base_by_manufacturer`. Một số tên dòng xe còn chưa gọn do quá trình chuẩn hóa, ví dụ Toyota có cả `rav` và `rav4`, Ford có `f250` và `f250sd`. C01 và E02 có thể gộp hoặc ẩn bớt khi hiển thị.
