"""Kiểm tra nhanh D01. Chạy từ thư mục gốc repo:  python tests/test_d01_schemas.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # thư mục gốc repo

from backend.schemas.vehicle_input import VehicleInput, InputValidationError
from backend.schemas.result_schema import CarCard, PriceResult, AnalysisResult

# 1. Dữ liệu hợp lệ, giống form gửi sang (ô nâng cao để trống)
form = {"user_name": "Duy", "manufacturer": "Ford", "model_base": "f150", "year": "2015",
        "type": "pickup", "odometer": 60000, "condition": "good", "fuel": "gas",
        "transmission": "automatic", "budget_max_usd": 20000, "drive": ""}
car = VehicleInput.from_dict(form)
assert car.validate() == [], car.validate()
print("1. Hợp lệ:", car.title)
print("   Dòng cho mô hình giá:", car.to_model_row())
print("   Yêu cầu gợi ý:", car.to_recommendation_query())

# 2. Dữ liệu sai -> phải báo đủ lỗi, không được dừng chương trình
bad = VehicleInput.from_dict({"manufacturer": "ford", "model_base": "camry", "year": 1980,
                              "type": "boat", "odometer": "abc", "condition": "good",
                              "fuel": "gas", "transmission": "automatic"})
try:
    bad.check()
    raise AssertionError("Lẽ ra phải báo lỗi")
except InputValidationError as e:
    errors = e.errors
    assert len(errors) == 5, errors
    print("2. Bắt được", len(errors), "lỗi:")
    for msg in errors:
        print("   -", msg)

# 3. Kết quả trả về giao diện
card = CarCard.from_row({"id": 7301583321, "manufacturer": "dodge", "model_base": "durango",
                         "year": 2013, "price": 18997, "odometer": 96475, "type": "suv",
                         "condition": "excellent", "fuel": "gas", "transmission": "automatic"},
                        score=0.92)
result = AnalysisResult(success=True, vehicle_title=car.title,
                        price=PriceResult(predicted_price=18500.0, model_name="HistGradientBoosting"),
                        top_matches=[card])
text = json.dumps(result.to_dict(), ensure_ascii=False)      # phải chuyển được sang JSON
print("3. Thẻ xe:", card.subtitle)
print("   Kết quả lỗi:", AnalysisResult.failure(errors).to_dict()["success"])
print("\nTẤT CẢ ĐỀU ĐẠT")