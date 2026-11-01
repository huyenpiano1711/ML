# D05 – Xử lý hình ảnh xe (`backend/services/image_service.py`)

Nhận đường dẫn ảnh trong catalog, kiểm tra ảnh dùng được hay không và luôn trả về một
đường dẫn ảnh mở được cho giao diện. Ảnh lỗi hoặc thiếu được thay bằng `assets/placeholder_car.png`.

## Cách dùng

```python
from backend.services.image_service import get_image_service

images = get_image_service()                 # tạo một lần cho cả phiên chạy
cards = images.with_images(result.to_cards())  # D06: image_path của mọi thẻ đều có giá trị

r = images.resolve_card(card)                # muốn biết chi tiết
r.path            # đường dẫn tuyệt đối, đưa thẳng vào QPixmap(r.path)
r.is_placeholder  # True nếu là ảnh thay thế
r.label           # "Ảnh minh họa dòng xe" hoặc "Chưa có ảnh minh họa" (chú thích dưới ảnh)
r.source          # catalog | lookup_exact | lookup_nearest_year | placeholder
r.reason          # lý do ảnh catalog không dùng được (ok nếu dùng được)
```

`with_images()` trả bản sao thẻ xe, không sửa thẻ gốc và không đổi `CarCard` (hợp đồng D01 giữ nguyên).

## Quy tắc tìm ảnh

1. `image_path` trong catalog (C01).
2. Nếu trống hoặc hỏng: tìm lại theo khóa `<hãng>_<dòng>_<năm>` trong `assets/car_images_unique`,
   cùng quy tắc `build_catalog.attach_images()`: đúng năm, nếu không có thì năm gần nhất của cùng dòng xe
   (bằng nhau thì lấy năm nhỏ hơn).
3. Ảnh thay thế.

Ảnh chỉ được dùng khi: nằm trong `assets/car_images_unique` (chặn đường dẫn `../`), đuôi `.jpg/.jpeg/.png`,
tồn tại, không rỗng, không quá 20 MB, Pillow đọc được phần đầu file và file có đủ dấu kết thúc
(JPEG `FF D9`, PNG `IEND`) - bắt được file tải dở mà không phải giải mã cả ảnh. Kết quả kiểm tra lưu đệm theo
(đường dẫn, thời điểm sửa, kích thước): mỗi ảnh chỉ đọc một lần; file bị thay thì được kiểm lại.

| `reason` | Trường hợp |
|---|---|
| `missing_path` | Catalog không có đường dẫn ảnh |
| `not_found` | File không tồn tại |
| `outside_image_dir` | Đường dẫn trỏ ra ngoài thư mục ảnh |
| `unsupported_format` | Không phải JPEG/PNG |
| `empty_file`, `too_large` | File rỗng hoặc quá 20 MB |
| `corrupt_image` | File không đọc được |

Nếu `assets/placeholder_car.png` bị xóa hoặc hỏng, service tự vẽ lại bằng Pillow.

## Kiểm thử và số liệu

- `tests/test_d05_image_service.py`: 25 test (ảnh hợp lệ, 9 kiểu lỗi, file JPEG/PNG bị cắt ngang, tìm lại theo năm, thẻ xe, ảnh thay thế bị xóa/hỏng, bộ đệm).
- `scripts/15_image_service_check.py` → `reports/integration/image_service_check.json`:
  - 6.842/6.842 ảnh trong `car_images_unique` đọc được.
  - 191.196 xe trong catalog: 99,0% có ảnh minh họa, 1,0% (1.904 xe, dòng xe không có ảnh nào) dùng ảnh thay thế.
  - Nếu catalog được build khi máy chưa có thư mục ảnh (`image_path` trống), bước tìm lại vẫn cho 99,0%
    (85,0% đúng năm, 14,0% năm gần nhất).

## Lưu ý cho nhóm

- `reports/recommendation/catalog_report.json` hiện ghi `image_dir_found: false`: catalog đang được build
  khi máy chưa có ảnh. Sau khi giải nén `car_images_unique_part1..3.zip` vào `assets/`, chạy lại
  `python -m src.recommendation.build_catalog` để catalog có sẵn `image_path` (85,0% đúng năm, 14,0% năm gần nhất).
- Ảnh là ảnh minh họa dòng xe từ Wikimedia Commons, không phải ảnh thật của từng tin; giao diện nên hiện `r.label`.
