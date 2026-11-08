# Hợp đồng dữ liệu vào/ra (D01)

## Đầu vào: `backend/schemas/vehicle_input.py`

Frontend gửi dict, Backend gọi:

```python
car = VehicleInput.from_dict(data).check()
```

Nếu dữ liệu không hợp lệ, `check()` phát sinh `InputValidationError` với danh sách
thông báo trong thuộc tính `errors`.

| Tên trường | Kiểu | Bắt buộc | Ô trên form |
|---|---|---|---|
| manufacturer | str | Có | Hãng xe (gõ tên hoặc chọn trong danh sách) |
| model_base | str | Có | Dòng xe (lọc theo hãng; gõ tên hoặc chọn) |
| year | int (1990–2022) | Có | Năm sản xuất |
| type | str hoặc None | Không (None → `unknown`) | Kiểu dáng (mặc định "Not sure") |
| odometer | float (0–400.000) | Có | Số miles đã đi |
| condition | str hoặc None | Không (None → `unknown`) | Tình trạng xe (mặc định "Not sure") |
| fuel | str hoặc None | Không (None → `unknown`) | Nhiên liệu (mặc định "Not sure") |
| transmission | str hoặc None | Không (None → `unknown`) | Hộp số (mặc định "Not sure") |
| budget_max_usd | float (1.000–150.000) | Có | Ngân sách tối đa |
| title_status, state | str hoặc None | Không | Tùy chọn nâng cao |
| drive, cylinders, paint_color | str hoặc None | Không | Không còn trên form (dữ liệu thiếu 27–35%); Backend vẫn nhận nếu gửi, bỏ trống → `unknown` |
| user_name | str | Không | Tên của tài khoản đã đăng nhập |

Giá trị hợp lệ của từng trường được lấy từ `allowed_values` và `ui_options`
trong `src/features/feature_schema.json`.

- `car.to_model_row()` tạo dict đầu vào cho mô hình dự đoán giá.
- `car.to_recommendation_query()` tạo truy vấn cho hệ thống gợi ý xe.
- `budget_max_usd` chỉ dùng cho Recommendation, không truyền vào mô hình giá.

## Đầu ra: `backend/schemas/result_schema.py`

```text
AnalysisResult
├── success: bool
├── vehicle_title: str
├── price: PriceResult
├── top_matches: list[CarCard]
├── similar_price: list[CarCard]
├── errors: list[str]
├── warnings: list[str]
└── elapsed_ms: float | None
```

`PriceResult` gồm giá dự đoán, khoảng giá tham khảo, đơn vị tiền tệ và tên mô hình.

`CarCard` gồm ID, hãng, dòng xe, năm, giá, số miles, kiểu xe, tình trạng,
nhiên liệu, hộp số, đường dẫn ảnh, điểm phù hợp, giấy tờ (`title_status`), bang (`state`)
và `fair_price`. Dữ liệu catalog được chuyển thành thẻ bằng `CarCard.from_row(row, score)`.
`fair_price` là giá mô hình ước tính cho chính tin đăng đó (theo năm, số miles, giấy tờ... của nó),
do `app_service` gắn bằng `estimate_card_prices()`; `None` khi mô hình lỗi hoặc dòng xe không có
trong danh sách của mô hình. Giao diện dùng nó để cảnh báo khi giá rao thấp hơn 70% giá đó,
và ghi "Rebuilt title", "Salvage title"... khi xe không có giấy tờ sạch.

Khi xử lý thất bại, Backend trả `AnalysisResult.failure(errors)` để Frontend
hiển thị lỗi mà không phải tự suy luận hoặc tạo dữ liệu.
