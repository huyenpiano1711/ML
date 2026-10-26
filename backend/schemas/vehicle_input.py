"""
vehicle_input.py - HỢP ĐỒNG DỮ LIỆU ĐẦU VÀO (Frontend -> Backend)

Quy định Frontend (form PyQt6, Màn hình 2) gửi cho Backend những thông tin gì,
mỗi thông tin tên gì, kiểu gì, giá trị hợp lệ ra sao.
Mọi danh sách giá trị hợp lệ đọc từ src/features/feature_schema.json (task A04),
nên form, mô hình và Backend luôn dùng chung một nguồn.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# 1. Đọc feature_schema.json một lần khi import
# ---------------------------------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parents[2]          # thư mục gốc repo
SCHEMA_PATH = PROJECT_DIR / "src" / "features" / "feature_schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

FEATURES = {f["name"]: f for f in SCHEMA["features"] if f["source"] == "user_input"}
MODELS_BY_MAKE = SCHEMA["options"]["model_base_by_manufacturer"]

REQUIRED_FIELDS = [n for n, f in FEATURES.items() if f["required"]]
OPTIONAL_FIELDS = [n for n, f in FEATURES.items() if not f["required"]]
NUMERIC_FIELDS = ["year", "odometer", "budget_max_usd"]


def _fmt(x, name):
    """2022 -> '2022' (năm không có dấu chấm); 400000 -> '400.000' (kiểu Việt Nam)."""
    return f"{x:.0f}" if name == "year" else f"{x:,.0f}".replace(",", ".")


class InputValidationError(ValueError):
    """Lỗi khi dữ liệu người dùng nhập không hợp lệ. .errors = danh sách thông báo."""

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


# ---------------------------------------------------------------------------
# 2. Cấu trúc dữ liệu Frontend gửi sang
# ---------------------------------------------------------------------------
@dataclass
class VehicleInput:
    # --- 1. Thông tin cơ bản (bắt buộc) ---
    manufacturer: str            # Hãng xe, ví dụ "ford"
    model_base: str              # Dòng xe, ví dụ "f150"
    year: int                    # Năm sản xuất, 1990-2022
    type: str                    # Kiểu dáng, ví dụ "pickup"
    # --- 2. Thông số kỹ thuật (bắt buộc) ---
    odometer: float              # Số miles đã đi, 0-400.000
    condition: str               # Tình trạng xe, ví dụ "good"
    fuel: str                    # Nhiên liệu, ví dụ "gas"
    transmission: str            # Hộp số, ví dụ "automatic"
    # --- 3. Ngân sách (bắt buộc) ---
    budget_max_usd: float        # Ngân sách tối đa (USD), 1.000-150.000
    # --- Tùy chọn nâng cao (None = người dùng bỏ trống) ---
    drive: Optional[str] = None
    cylinders: Optional[str] = None
    paint_color: Optional[str] = None
    title_status: Optional[str] = None
    state: Optional[str] = None
    # --- Màn hình 1 (chỉ để hiển thị, không đưa vào mô hình) ---
    user_name: str = ""

    # ------------------------------------------------------------------
    @classmethod
    def from_dict(cls, data: dict) -> "VehicleInput":
        """Tạo VehicleInput từ dict mà Frontend gửi sang.
        Chuẩn hóa: bỏ khoảng trắng, chữ thường, ô trống -> None, số -> int/float.
        Chưa kiểm tra hợp lệ: gọi .validate() hoặc .check() sau đó."""
        clean = {}
        for name in REQUIRED_FIELDS + OPTIONAL_FIELDS:
            value = data.get(name)
            if isinstance(value, str):
                value = value.strip().lower()
                if value in ("", "unknown", "không rõ"):
                    value = None
            clean[name] = value
        for name in NUMERIC_FIELDS:
            if clean[name] is not None:
                try:
                    clean[name] = float(clean[name])
                except (TypeError, ValueError):
                    pass                      # để validate() báo lỗi kiểu dữ liệu
        if isinstance(clean["year"], float) and clean["year"].is_integer():
            clean["year"] = int(clean["year"])
        clean["user_name"] = str(data.get("user_name") or "").strip()
        return cls(**clean)

    # ------------------------------------------------------------------
    def validate(self) -> list[str]:
        """Trả về danh sách lỗi (tiếng Việt). Danh sách rỗng = hợp lệ."""
        errors = []
        # (a) Ô bắt buộc không được trống
        for name in REQUIRED_FIELDS:
            if getattr(self, name) is None:
                errors.append(f"Chưa nhập '{FEATURES[name]['ui_label']}'.")
        # (b) Ô số: đúng kiểu và nằm trong khoảng
        for name in NUMERIC_FIELDS:
            value, f = getattr(self, name), FEATURES[name]
            if value is None:
                continue
            if not isinstance(value, (int, float)):
                errors.append(f"'{f['ui_label']}' phải là số.")
            elif not f["min"] <= value <= f["max"]:
                lo, hi = _fmt(f["min"], name), _fmt(f["max"], name)
                errors.append(f"'{f['ui_label']}' phải từ {lo} đến {hi}.")
        # (c) Ô chọn: giá trị phải nằm trong danh sách mô hình đã học
        for name, f in FEATURES.items():
            value = getattr(self, name)
            if f["dtype"] == "categorical" and name != "model_base" and value is not None:
                if value not in f["allowed_values"]:
                    errors.append(f"'{f['ui_label']}' không hợp lệ: {value!r}.")
        # (d) Dòng xe phải thuộc hãng đã chọn
        if self.manufacturer and self.model_base:
            if self.model_base not in MODELS_BY_MAKE.get(self.manufacturer, []):
                errors.append(f"Dòng xe {self.model_base!r} không thuộc hãng {self.manufacturer!r}.")
        return errors

    def check(self) -> "VehicleInput":
        """Như validate() nhưng ném InputValidationError nếu có lỗi."""
        errors = self.validate()
        if errors:
            raise InputValidationError(errors)
        return self

    # ------------------------------------------------------------------
    def to_model_row(self) -> dict:
        """Một dòng dữ liệu cho mô hình dự đoán giá (B06 / D02).
        Tên cột trùng với dữ liệu huấn luyện. Ô nâng cao bỏ trống được thay theo
        quy tắc 'default' trong feature_schema.json:
          drive, cylinders, paint_color -> 'unknown' (drive/cylinders sẽ được
          GroupModeImputer trong pipeline suy ra từ hãng + dòng + năm);
          title_status, state -> giá trị phổ biến nhất trong tập train.
        Các cột tính thêm (car_age, log_odometer, make_model...) do predict.py tính."""
        row = {name: getattr(self, name) for name in REQUIRED_FIELDS if name != "budget_max_usd"}
        for name in OPTIONAL_FIELDS:
            value = getattr(self, name)
            row[name] = value if value is not None else FEATURES[name]["default"]
        return row

    def to_recommendation_query(self) -> dict:
        """Yêu cầu gửi cho chức năng gợi ý xe (C02 / C03 / D03)."""
        prefs = {name: getattr(self, name) for name, f in FEATURES.items()
                 if "recommendation" in f["used_in"] and name != "budget_max_usd"}
        return {"budget_max_usd": self.budget_max_usd,
                "preferences": {k: v for k, v in prefs.items() if v is not None}}

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def title(self) -> str:
        """Tên xe để hiển thị, ví dụ 'Ford F150 2015'."""
        make, model = (self.manufacturer or "").title(), (self.model_base or "").title()
        return f"{make} {model} {self.year or ''}".strip()