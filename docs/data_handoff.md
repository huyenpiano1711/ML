# Bàn giao dữ liệu – data-v1

Bản dữ liệu dùng chung cho các phần dự đoán giá, gợi ý xe và giao diện. Tải các file `.zip` ở mục Releases (bản `data-v1`), giải nén theo hướng dẫn trong `README.md`.

## Các file

| File | Kích thước | Mô tả |
|---|---|---|
| `data/raw/vehicles.csv` | 426.880 × 26 | Dữ liệu gốc Craigslist (Kaggle) |
| `data/interim/desc_features.csv` | 426.880 × 16 | `id` + 15 đặc trưng từ cột mô tả (`desc_*`, 12 cờ `kw_*`) |
| `data/interim/vins_to_decode.csv` | 96.267 dòng | VIN hợp lệ đã gửi tra cứu |
| `data/interim/vin_decoded.csv` | 96.267 dòng | Kết quả giải mã VIN từ API NHTSA vPIC |
| `data/processed/vehicles_clean.pkl` / `.csv` | 198.514 × 48 | Dữ liệu sau 16 bước làm sạch, kèm 29 đặc trưng mới |
| `data/processed/vehicles_filled.pkl` / `.csv` | 198.514 × 65 | **Dữ liệu dùng cho mô hình**: dữ liệu sạch + 5 cột thông số đã điền + đặc trưng từ VIN |
| `assets/car_images_unique/` | 6.842 ảnh | Ảnh minh họa theo khóa `hang_dong_nam.jpg` (ví dụ `ford_f150_2015.jpg`) |

Khóa chính của mọi bảng là `id` (mã tin đăng, `int64`). Nên đọc file `.pkl` vì giữ đúng kiểu dữ liệu và nhanh hơn `.csv`.

## Cột chính trong `vehicles_filled.pkl`

- **Mục tiêu:** `price` (USD, 1.000–150.000), `log_price` = log(1 + price).
- **Thông tin xe:** `manufacturer`, `model_base`, `make_model`, `year`, `car_age`, `odometer`, `condition`, `title_status`, `paint_color`, `state`, `seller_type`.
- **Thông số đã điền:** `drive_filled`, `cylinders_filled`, `type_filled`, `fuel_filled`, `transmission_filled`. Giá trị gốc vẫn ở cột không có hậu tố; nguồn của giá trị điền ở cột `*_source`: `listing`, `vin`, `group` hoặc `unknown`.
- **Từ VIN** (chỉ có ở 48% số tin): `vin_trim`, `vin_displacement_l`, `vin_engine_hp`, `vin_doors`, `vin_decoded`.

Mô tả đầy đủ từng cột: `reports/data_dictionary.csv`.

## Lưu ý khi dùng

- **Rò rỉ dữ liệu:** cột `*_filled` có nguồn `group` được tính trên toàn bộ dữ liệu. Khi huấn luyện, dùng `GroupModeImputer` (`src/features`) fit trên tập train, như trong `scripts/09_fill_experiment.py`.
- **Bước G1** (loại 2.920 tin ngoại lai theo nhóm hãng + dòng + năm) đã chạy trên toàn bộ dữ liệu trước khi chia tập; cần kiểm tra lại trước khi huấn luyện chính thức.
- `condition` và `paint_color` còn khoảng 38% và 28% `unknown`; nhóm chủ đích không điền hai cột này.
- Giá là giá niêm yết tại Mỹ năm 2021, không phải giá giao dịch.
- Ảnh là ảnh minh họa dòng xe từ Wikimedia Commons, không phải ảnh thật của từng tin; nhiều ảnh không đúng đời xe. Khi hiển thị, ghi "ảnh minh họa" kèm tác giả và giấy phép.

## Kiểm tra toàn vẹn (SHA-256)

```
94eb41fd17540876b1bb24745a01486818b42628c8d5f921dd4f6a9dce4cfb82  autowise_data_interim.zip
905bc8a4dbbbc0db059643b0a8dad9ec44e4db9752a7d1c700b7cffe1226e2b9  autowise_data_processed.zip
7c56d482520443d789d0e0388538a50e6ae5399a39952e3dedf1ee2ba742c6a1  car_images_unique_part1.zip
f8831f8e2dff3804d60703e73b88d4e2d87e8e53fb7297f0658f795dd81b6d5c  car_images_unique_part2.zip
f61e464390a5a9cfc22d6c0e47463341abb4cc9eece323a27f2ac15cb496d12f  car_images_unique_part3.zip
d3370a19e160117d95e279d6f601626a0aed80f42af7a97ef6db22434ac504c3  vehicles_raw.zip
```
