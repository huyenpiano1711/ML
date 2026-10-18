# 🚘 AutoWiseAI

Hệ thống phân tích, định giá xe ô tô đã qua sử dụng và xây dựng tập dữ liệu đa phương thức (Multimodal Car Valuation).

## 📁 Cấu Trúc Dự Án

* **`assets/car_images/`**: Thư mục lưu trữ hơn 5,000+ hình ảnh xe chất lượng cao (~1.3 GB) được tải từ Wikimedia Commons.
* **`data/`**:
  * `vehicles_clean.csv`: Bộ dữ liệu 198,436 xe với 48 đặc trưng kỹ thuật & thị trường.
  * `image_manifest.csv`: Danh mục quản lý hình ảnh, tác giả, đường dẫn và bản quyền.
  * `vehicles_with_images.csv`: Tập dữ liệu hoàn chỉnh ghép nối thông tin xe với ảnh cục bộ.
* **`scripts/`**:
  * `download_car_images.py`: Script thu thập và chuẩn hóa ảnh xe tự động từ Wikimedia Commons.
* **`DATA_DESCRIPTION.md`**: **Tài liệu chi tiết mô tả dữ liệu bảng, từ điển 48 cột, phương pháp thu thập hình ảnh và bản quyền**.

## 📖 Xem Tài Liệu Dữ Liệu Chi Tiết

Vui lòng xem chi tiết tại: [DATA_DESCRIPTION.md](file:///d:/AutoWiseAI/DATA_DESCRIPTION.md)
