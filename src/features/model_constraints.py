"""
model_constraints.py - Ràng buộc theo dòng xe, lấy từ dữ liệu thật (src/features/model_constraints.json).

Vì sao cần: form cho chọn tự do mọi tổ hợp, nên người dùng có thể nhập "Lexus RX300 2020 chạy dầu"
- một chiếc xe không có trong thực tế (RX300 chỉ có 1999-2003, chạy xăng). Mô hình vẫn trả một con số,
nhưng đó là ngoại suy ngoài vùng dữ liệu đã học. Tổng quan đồ án yêu cầu: "Các trường trên giao diện
phải tương ứng với dữ liệu và những chức năng Backend thực sự hỗ trợ."

Quy tắc (xem scripts/18_build_model_constraints.py):
  - year: từ năm nhỏ nhất đến lớn nhất có >= 2 tin đăng, nới thêm 1 năm mỗi đầu nếu năm đó có tin.
  - type / fuel / transmission: giá trị có >= 5 tin hoặc >= 10% số tin của dòng xe ('unknown' bỏ qua).
Dòng xe không có trong file -> không ràng buộc (dùng toàn bộ lựa chọn của feature_schema.json).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

CONSTRAINTS_PATH = Path(__file__).resolve().parent / "model_constraints.json"
CATEGORICAL = ("type", "fuel", "transmission")


@lru_cache(maxsize=1)
def load_constraints(path: str = str(CONSTRAINTS_PATH)) -> dict:
    p = Path(path)
    if not p.is_file():
        return {}
    return json.loads(p.read_text(encoding="utf-8")).get("models", {})


def constraints_for(manufacturer, model_base) -> dict | None:
    """{'n', 'year': [min, max], 'type': [...], 'fuel': [...], 'transmission': [...]} hoặc None."""
    if not manufacturer or not model_base:
        return None
    return load_constraints().get(str(manufacturer), {}).get(str(model_base))


def violations(vehicle) -> list[tuple[str, object]]:
    """Các ô vi phạm ràng buộc của dòng xe: [(tên ô, giá trị cho phép)], rỗng = hợp lệ.
    tên ô 'year' -> (min, max); các ô khác -> danh sách giá trị cho phép."""
    c = constraints_for(getattr(vehicle, "manufacturer", None), getattr(vehicle, "model_base", None))
    if not c:
        return []
    out = []
    year = getattr(vehicle, "year", None)
    if isinstance(year, (int, float)) and not c["year"][0] <= year <= c["year"][1]:
        out.append(("year", tuple(c["year"])))
    for name in CATEGORICAL:
        value = getattr(vehicle, name, None)
        if value is not None and c.get(name) and value not in c[name]:
            out.append((name, c[name]))
    return out
