# C01–C04 – Gợi ý xe (Vehicle Recommendation)

Mã: `src/recommendation/` · Kiểm thử: `tests/test_c_recommendation.py` · Dữ liệu vào: `data/processed/vehicles_filled.pkl` (data-v1)

## Cách chạy

```bash
pip install -r requirements.txt            # cần thêm scipy (đã có sẵn khi cài scikit-learn)
python -m src.recommendation.build_catalog # C01 -> data/processed/recommendation_catalog.pkl
python -m src.recommendation.evaluate      # C04 -> reports/recommendation/evaluation_results.csv/.json/.png
python tests/test_c_recommendation.py      # kiểm thử bằng dữ liệu giả lập (không cần dataset)
```

`*.pkl` nằm trong `.gitignore`: đính `recommendation_catalog.pkl` vào Release mới (ví dụ `data-v2`) hoặc `git add -f`.

## C01 – Catalog (`build_catalog.py`)

| Bước | Nội dung |
|---|---|
| Cột | `id, manufacturer, model_base, make_model, year, car_age, price, odometer, type, condition, fuel, transmission, drive, image_path, image_match` (trùng `recommendation_columns.display` và `CarCard`) |
| Nguồn thông số | `type/fuel/transmission/drive` lấy từ cột `*_filled`; `condition` giữ nguyên (nhóm chủ đích không điền, ~38% `unknown`) |
| Tin lặp | Bỏ tin cùng hãng, dòng, năm, giá, odometer, kiểu dáng, nhiên liệu, hộp số, dẫn động, tình trạng (cùng xe đăng nhiều khu vực), giữ `id` nhỏ nhất. Số dòng bị bỏ ghi trong `catalog_report.json` |
| Kiểm tra | `id` không trùng; cột bắt buộc không thiếu; giá, odometer, năm nằm trong ngưỡng của `src/config.py`. Sai thì dừng, không lưu |
| Ảnh | Khóa `<hang>_<dong>_<nam>.jpg` (cùng quy tắc `download_car_images.py`). `image_match`: `exact`, `nearest_year` (cùng dòng, năm gần nhất) hoặc `none` (`image_path = None`, Frontend dùng ảnh thay thế) |

Chỉ có 6.842 ảnh cho hàng chục nghìn cặp (dòng, năm), nên nhiều xe sẽ là `nearest_year` hoặc `none`. Ảnh chỉ là ảnh minh họa dòng xe, giao diện cần ghi "ảnh minh họa".

## C02 – Lọc (`Recommender.valid_indices`)

- Bắt buộc, theo `feature_schema.json`: `price <= budget_max_usd`.
- Loại các `id` trong `exclude_ids`.
- Tùy chọn `strict=("type", "fuel", ...)`: biến trường đó thành điều kiện bắt buộc. Mặc định để trống, vì form cho phép chọn nhiều ô và đòi khớp cả sáu sẽ dễ ra 0 xe.
- Không có xe nào ≤ ngân sách: trả danh sách rỗng kèm `warnings`; ít hơn 5 xe: trả số xe tìm được kèm cảnh báo. Không bao giờ vượt ngân sách.

## C03 – Xếp hạng (`Recommender.recommend`)

Mã hóa: `price` (log, thang 1.000–150.000), `car_age`, `odometer`, `condition` (thứ bậc) và cờ `condition_unknown` thuộc nhóm số; `manufacturer, model_base, type, fuel, transmission, drive` dùng one-hot. Mỗi thành phần nhân trọng số `DEFAULT_WEIGHTS`; ô người dùng bỏ trống có trọng số 0.

| Phương pháp | Điểm 0–1 |
|---|---|
| `knn` (mặc định) – khoảng cách Euclid có trọng số | `1 − d / d_max` |
| `cosine` – cùng không gian đặc trưng | độ tương đồng cosine |

- Giá mục tiêu = 85% ngân sách (`PRICE_TARGET_RATIO`), để không ép người dùng dùng hết ngân sách.
- Mỗi cặp (dòng xe, năm) chọn tối đa 1 xe (`max_per_group`), tránh Top 5 là năm tin đăng lặp của cùng một xe.
- So với `recommendation_columns` trong schema, C03 **thêm `model_base`** vào phần độ tương đồng vì form bắt buộc nhập Dòng xe. Nếu muốn Top 5 đa dạng dòng xe hơn, giảm `weights["model_base"]`.
- Cosine với thuộc tính số có điểm yếu: cosine đo góc nên hai xe cùng tỷ lệ (tuổi, odometer) nhưng khác độ lớn vẫn rất "giống". Vì vậy mặc định là KNN; `evaluate.py` đo cả hai để nhóm chọn dựa trên số liệu.
- Tính trên ma trận thưa, ~20 ms/truy vấn với 198 nghìn xe (máy thử nghiệm, dữ liệu giả lập). Kết quả được kiểm chứng trùng `sklearn.neighbors.NearestNeighbors(algorithm="brute")` trong test.

### Xe cùng mức giá (`Recommender.similar_price`)

Quy tắc lọc, không dùng mô hình: giá trong ±10% giá dự đoán (mở rộng 15% → 20% → 30% nếu chưa đủ 6 xe), loại 5 xe Top 5, xếp theo độ giống sở thích (bỏ thành phần giá), mỗi dòng xe tối đa 1 xe. Danh sách này **không bị chặn bởi ngân sách**, vì tham chiếu là giá dự đoán; nếu nhóm muốn chặn thì thêm bước lọc ở Backend.

## Tích hợp Backend (D03)

```python
from src.recommendation.recommend import Recommender
rec  = Recommender.from_pickle()                        # nạp một lần khi khởi động
car  = VehicleInput.from_dict(data).check()
top  = rec.recommend(car.to_recommendation_query())     # RecommendationResult
alt  = rec.similar_price(price.predicted_price, exclude_ids=top.cars["id"],
                         preferences=car.to_recommendation_query()["preferences"])
result = AnalysisResult(success=True, ..., top_matches=top.to_cards(), similar_price=alt.to_cards(),
                        warnings=top.warnings + alt.warnings)
```

`RecommendationResult`: `cars` (DataFrame), `warnings`, `n_candidates`, `elapsed_ms`, `method`, `to_cards()`.

## C04 – Đánh giá (`evaluate.py`)

So `knn`, `cosine` với hai baseline cùng bộ lọc ngân sách: `baseline_random` và `baseline_budget` (xe giá sát ngân sách nhất). Hai bộ truy vấn (mặc định 300 mỗi bộ, `seed=42`):

- `from_listing`: lấy từ một tin thật (bỏ chính tin đó khỏi ứng viên), ngân sách = giá × U(1,0–1,5).
- `random_form`: tổ hợp ngẫu nhiên các ô trên form, gồm cả tổ hợp hiếm. Dùng đo độ phủ và thời gian.

| Chỉ số | Ý nghĩa |
|---|---|
| `hard_constraint_rate_pct` | % xe trả về có giá ≤ ngân sách (kiểm tra độc lập trên catalog), phải = 100 |
| `coverage_5_pct` | % truy vấn trả đủ 5 xe |
| `precision_at_5_proxy_pct` | % xe cùng dòng xe và lệch năm ≤ 2 so với tin gốc (chỉ `from_listing`) |
| `mean_score_common` | điểm KNN 0–1 tính cùng một công thức cho mọi phương pháp |
| `mean_distinct_models` | số dòng xe khác nhau trong Top 5 |
| `latency_mean_ms`, `latency_p95_ms` | thời gian trả kết quả |

**Hạn chế phải ghi trong báo cáo:** `precision_at_5_proxy` không dựa trên nhãn ưa thích của người dùng thật, nó đo mức nhất quán với yêu cầu đầu vào. Vì bộ trọng số ưu tiên đúng dòng xe nên chỉ số này nghiêng về KNN/Cosine so với baseline; không nên diễn giải như "độ hài lòng".

## Việc cần làm tiếp

1. Tải `autowise_data_processed.zip`, chạy `build_catalog`, chạy `evaluate`, và chỉ dùng số liệu từ lần chạy này trong báo cáo.
2. Chốt `knn` hay `cosine` theo bảng kết quả, ghi lý do.
3. Báo TV1 (Backend) về kịch bản ít hơn 5 xe/không có xe (`warnings`) và TV5 (Frontend) về ảnh `None`.
4. Sau khi quyết định xử lý bước G1 (rò rỉ ngoại lai), chạy lại `build_catalog` trên bản dữ liệu cuối.
