# Backend – luồng xử lý chính, kiểm thử và hiệu năng

## Dùng từ Frontend

```python
from backend.app_service import analyze, get_app_service

get_app_service().warm_up()   # main.py, lúc mở ứng dụng: nạp sẵn mô hình, catalog, danh mục ảnh
result = analyze(form_dict)   # khi bấm "Phân tích và tìm xe" -> AnalysisResult, không bao giờ ném lỗi
```

`form_dict` dùng đúng tên trường trong `docs/input_output_contract.md`. Giao diện chỉ cần đọc:

| Trường | Hiển thị |
|---|---|
| `result.errors` | Có lỗi thì hiện thông báo (đã viết sẵn bằng tiếng Việt) |
| `result.warnings` | Nhắc nhở, không chặn kết quả |
| `result.price` | Giá dự đoán, khoảng giá tham khảo (`price_low`–`price_high`) |
| `result.top_matches` | Tối đa 5 thẻ xe phù hợp, có `score` |
| `result.similar_price` | Tối đa 6 thẻ xe cùng mức giá |
| `card.image_path` | Luôn là đường dẫn ảnh mở được: `QPixmap(card.image_path)` |

## Luồng `analyze()`

1. Kiểm tra dữ liệu nhập; sai thì trả `AnalysisResult.failure(errors)` ngay, không gọi mô hình.
2. Dự đoán giá (`prediction_service`).
3. Gợi ý tối đa 5 xe trong ngân sách (`recommendation_service`).
4. Tìm tối đa 6 xe cùng mức giá, không trùng Top 5 (`alternative_service`).
5. Gắn ảnh cho mọi thẻ xe (`image_service`).
6. Gom kết quả, lỗi, cảnh báo, thời gian vào `AnalysisResult`.

**Quy ước lỗi.** Thành phần nào lỗi thì thêm thông báo vào `errors` (`success = False`) nhưng vẫn trả
phần kết quả còn lại: mô hình lỗi vẫn có Top 5; catalog lỗi vẫn có giá. Không đủ xe, giá dự đoán cao hơn
ngân sách hay phải mở rộng khoảng giá là `warnings`. Ảnh thiếu/lỗi không tạo lỗi (dùng ảnh thay thế).
Lỗi bất ngờ ở bất kỳ bước nào cũng được bắt lại và ghi log `autowise.backend`.

**Nạp một lần.** Mô hình (`load_pipeline`, có bộ đệm), catalog và dịch vụ ảnh được nạp ở lần đầu và
dùng lại. Nếu nạp catalog lỗi (chưa build), lần bấm sau sẽ thử lại. Thời gian từng bước của lần gọi
gần nhất: `get_app_service().last_timings` (ms).

## Kiểm thử – `tests/test_backend.py` (31 test)

| Nhóm | Trường hợp |
|---|---|
| Luồng đầy đủ | Có giá, ≤ 5 xe trong ngân sách, ≤ 6 xe cùng giá không trùng Top 5, mọi ảnh mở được, kết quả chuyển JSON được |
| Nhất quán | Giá qua Backend = giá gọi trực tiếp `predict_price()` |
| Nhập thiếu / sai | Thiếu ô, chữ ở ô số, năm/số miles/ngân sách ngoài khoảng, giá trị không hợp lệ, dòng xe không thuộc hãng, form rỗng, dữ liệu không phải dict, chữ hoa/khoảng trắng/ô thừa |
| Không tìm thấy xe | Không xe nào trong ngân sách; không xe nào cùng mức giá |
| Lỗi nạp | Thiếu file mô hình, file mô hình hỏng, thiếu catalog, catalog lỗi rồi được tạo lại, bộ gợi ý lỗi, lỗi bất ngờ |
| Thiếu ảnh | Ảnh hỏng/thiếu dùng ảnh thay thế; dịch vụ ảnh lỗi không làm hỏng kết quả |
| Hiệu năng | 5 lần bấm: mô hình nạp 1 lần, catalog nạp 1 lần |
| Dữ liệu thật | Chạy với `recommendation_catalog.pkl` thật (bỏ qua nếu chưa build) |

Chạy: `python -m pytest -q` (toàn repo: 84 test).

## Hiệu năng – `scripts/16_backend_performance.py`

300 yêu cầu từ xe thật trong tập test (chỉ dòng xe có trên form) + 10 yêu cầu sai →
`reports/integration/backend_performance.csv` (theo bước), `backend_performance_requests.csv` (từng yêu cầu),
`backend_performance.json` (tóm tắt).

| Bước | Trung bình (ms) | p95 (ms) |
|---|---|---|
| Kiểm tra dữ liệu | 0,08 | 0,16 |
| Dự đoán giá | 34,5 | 51,1 |
| Gợi ý Top 5 | 22,4 | 33,2 |
| Xe cùng mức giá | 14,0 | 17,8 |
| Gắn ảnh | 69,4 | 153,2 |
| **Tổng** | **140,5** | **231,1** |

- Tỷ lệ lỗi với yêu cầu hợp lệ: 0%; 10/10 yêu cầu sai bị từ chối kèm thông báo.
- 100% yêu cầu có đủ 5 xe và 6 xe cùng giá; Top 5 luôn trong ngân sách, không trùng danh sách cùng giá.
- Mô hình nạp 1 lần, dùng lại 300 lần; catalog nạp 1 lần. Nạp lúc mở ứng dụng: khoảng 1,6 s.
- Số liệu đo trong máy ảo đọc ổ đĩa Windows qua thư mục chia sẻ (mở file chậm hơn chạy trực tiếp),
  nên là mức trên; bước gắn ảnh chủ yếu là thời gian mở file ảnh lần đầu. Nên chạy lại trên máy demo.
- Mô hình được lưu bằng scikit-learn 1.9.1; máy chạy phải dùng cùng phiên bản để tránh cảnh báo
  `InconsistentVersionWarning`.
