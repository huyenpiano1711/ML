"""
result_schema.py - HỢP ĐỒNG DỮ LIỆU ĐẦU RA (Backend -> Frontend)

Quy định Backend trả kết quả cho Màn hình 3 theo cấu trúc nào:
  1. Giá xe dự đoán            -> PriceResult
  2. Top 5 xe phù hợp          -> danh sách CarCard
  3. Các xe khác cùng mức giá  -> danh sách CarCard
Tất cả gói trong AnalysisResult. Giao diện chỉ đọc các trường ở đây, không tự tạo số liệu.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Optional

TOP_K = 5                  # số xe tối đa trong Top 5 (ML Draft)
MAX_ALTERNATIVES = 6       # số xe "cùng mức giá" tối đa - thống nhất lại với người làm D04
CURRENCY = "USD"


@dataclass
class CarCard:
    """Một thẻ xe trên Màn hình 3. Tên trường trùng recommendation_columns.display
    trong feature_schema.json và trùng cột của recommendation_catalog.pkl (C01)."""
    id: int                          # mã tin đăng
    manufacturer: str
    model_base: str
    year: int
    price: float                     # giá niêm yết (USD)
    odometer: float                  # số miles
    type: str
    condition: str
    fuel: str
    transmission: str
    image_path: Optional[str] = None # None -> image_service (D05) dùng ảnh thay thế
    score: Optional[float] = None    # độ phù hợp 0-1 (chỉ Top 5); None với xe cùng giá

    @classmethod
    def from_row(cls, row, score: Optional[float] = None) -> "CarCard":
        """Tạo thẻ xe từ 1 dòng catalog (dict hoặc pandas Series)."""
        image = row.get("image_path")
        if isinstance(image, float) and math.isnan(image):
            image = None
        return cls(id=int(row["id"]), manufacturer=str(row["manufacturer"]),
                   model_base=str(row["model_base"]), year=int(row["year"]),
                   price=float(row["price"]), odometer=float(row["odometer"]),
                   type=str(row["type"]), condition=str(row["condition"]),
                   fuel=str(row["fuel"]), transmission=str(row["transmission"]),
                   image_path=image, score=None if score is None else float(score))

    @property
    def title(self) -> str:
        return f"{self.manufacturer.title()} {self.model_base.title()} {self.year}"

    @property
    def subtitle(self) -> str:
        """Dòng phụ trên thẻ: Hãng · Dòng xe · Năm · Mileage · Tình trạng (theo ML Draft)."""
        miles = f"{self.odometer:,.0f}".replace(",", ".")          # 96475 -> 96.475
        return (f"{self.manufacturer.title()} · {self.model_base.title()} · {self.year} · "
                f"{miles} miles · {self.condition}")


@dataclass
class PriceResult:
    """Phần 1 của Màn hình 3: giá dự đoán."""
    predicted_price: float           # USD, đã đổi ngược từ log_price bằng np.expm1
    price_low: Optional[float] = None    # khoảng tham khảo (vd giá ± MAE) - do B04/B06 quyết định
    price_high: Optional[float] = None
    currency: str = CURRENCY
    model_name: str = ""             # vd "HistGradientBoosting" - để hiển thị/ghi báo cáo


@dataclass
class AnalysisResult:
    """Toàn bộ kết quả Backend trả cho giao diện sau khi bấm 'Phân tích và tìm xe'."""
    success: bool
    vehicle_title: str = ""                              # vd "Ford F150 2015"
    price: Optional[PriceResult] = None
    top_matches: list[CarCard] = field(default_factory=list)      # tối đa TOP_K
    similar_price: list[CarCard] = field(default_factory=list)    # tối đa MAX_ALTERNATIVES
    errors: list[str] = field(default_factory=list)       # lỗi chặn (nhập sai, lỗi mô hình)
    warnings: list[str] = field(default_factory=list)     # nhắc nhở (vd không đủ 5 xe)
    elapsed_ms: Optional[float] = None                     # thời gian xử lý (D08)

    @classmethod
    def failure(cls, errors) -> "AnalysisResult":
        """Kết quả khi có lỗi: giao diện chỉ cần hiển thị danh sách errors."""
        return cls(success=False, errors=list(errors))

    def to_dict(self) -> dict:
        """Chuyển sang dict thuần (dùng để in, lưu JSON, viết test)."""
        return asdict(self)