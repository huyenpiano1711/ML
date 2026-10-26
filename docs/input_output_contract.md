# Hợp đồng dữ liệu vào/ra (D01)

## Đầu vào: `backend/schemas/vehicle_input.py`

Frontend gửi dict, Backend gọi:
    car = VehicleInput.from_dict(data).check()   # sai -> InputValidationError(.errors)

| Tên trường | Kiểu | Bắt buộc | Ô trên form |
|---|---|---|---|
| manufacturer | str | Có | Hãng xe |
| model_base | str | Có | Dòng xe (lọc theo hãng) |
| year | int (1990–2022) | Có | Năm sản xuất |
| type | str | Có | Kiểu dáng |
| odometer | float (0–400.000) | Có | Số miles đã đi |
| condition | str | Có | Tình trạng xe |
| fuel | str | Có | Nhiên liệu |
| transmission | str | Có | Hộp số |
| budget_max_usd | float (1.000–150.000) | Có | Ngân sách tối đa |
| drive, cylinders, paint_color, title_status, state | str hoặc None | Không | Tùy chọn nâng cao |
| user_name | str | Không | Màn hình 1 |

Giá trị hợp lệ của từng ô: `allowed_values` / `ui_options` trong `src/features/feature_schema.json`.

- `car.to_model_row()` -> dict cho mô hình giá (D02). Cột tính thêm do predict.py tính.
- `car.to_recommendation_query()` -> {"budget_max_usd", "preferences"} cho gợi ý (D03).

## Đầu ra: `backend/schemas/result_schema.py`

AnalysisResult
├── success: bool
├── vehicle_title: str
├── price: PriceResult (predicted_price, price_low, price_high, currency, model_name)
├── top_matches: list[CarCard]   (tối đa 5)
├── similar_price: list[CarCard] (tối đa 6)
├── errors / warnings: list[str]
└── elapsed_ms: float

CarCard: id, manufacturer, model_base, year, price, odometer, type, condition,
fuel, transmission, image_path, score. Tạo từ một dòng catalog: CarCard.from_row(row, score).

Lỗi: return AnalysisResult.failure(errors), giao diện chỉ hiển thị errors.