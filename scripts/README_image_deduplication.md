# 🚘 AutoWiseAI - Vehicle Image Deduplication & Integrity Tool

Tài liệu hướng dẫn sử dụng công cụ kiểm tra, nhận diện trùng lặp và bảo vệ tính toàn vẹn của tập ảnh xe trong dự án **AutoWiseAI**.

---

## 📌 1. Mục Tiêu & Nguyên Tắc An Toàn

Công cụ được thiết kế để phân loại 2 dạng trùng lặp hình ảnh:
1. **Trùng lặp nhị phân tuyệt đối (Exact Duplicates)**: Hai file có nội dung nhị phân giống nhau 100% nhưng khác tên file (nhận diện qua mã băm **SHA-256**).
2. **Trùng lặp thị giác (Near Duplicates)**: Các ảnh trực quan gần như giống hệt nhau (do nén, đổi độ phân giải, đổi định dạng) nhưng mã băm SHA khác nhau (nhận diện qua **pHash** và thuật toán cây **BK-Tree**).

### 🛡️ Nguyên Tắc An Toàn Cốt Lõi:
* **Chế độ mặc định luôn là DRY RUN**: Không xóa, không đổi tên, không di chuyển bất kỳ tệp ảnh gốc nào.
* **Bảo vệ toàn vẹn CSV gốc**: Tuyệt đối không ghi đè trực tiếp lên các tệp CSV gốc (`vehicles_clean.csv`, `image_manifest.csv`).
* **Ưu tiên ảnh tham chiếu**: Luôn giữ lại ảnh có số lần tham chiếu nhiều nhất trong tập dữ liệu bảng để tránh làm gãy liên kết dữ liệu.
* **Xem xét trực quan (Human-in-the-loop)**: Toàn bộ ảnh near-duplicate đều được xuất thành bảng ảnh so sánh trực quan (Contact Sheets) để người dùng đánh giá trước khi quyết định.

---

## 🚀 2. Cài Đặt Thư Viện

Trước khi chạy, đảm bảo đã cài đặt các phụ thuộc cần thiết:

```bash
pip install -r scripts/requirements_image_cleaning.txt
```
*(Bao gồm: `Pillow`, `ImageHash`, `PyWavelets`, `pandas`, `numpy`, `tqdm`)*

---

## 🔍 3. Hướng Dẫn Chạy Quét An Toàn (Dry-Run Scan)

### Chạy quét toàn bộ (mặc định Dry Run):
```powershell
python scripts/deduplicate_car_images.py --dry-run
```

### Các tùy chọn nâng cao:
* **Điều chỉnh số luồng CPU**:
  ```powershell
  python scripts/deduplicate_car_images.py --workers 12
  ```
* **Điều chỉnh ngưỡng tương đồng pHash**:
  * `--strong-thresh 4`: Khoảng cách Hamming <= 4 xem là ứng viên trùng lặp mạnh (mặc định: 4).
  * `--review-thresh 8`: Khoảng cách Hamming <= 8 xem là ứng viên cần đánh giá (mặc định: 8).
  ```powershell
  python scripts/deduplicate_car_images.py --strong-thresh 3 --review-thresh 7
  ```
* **Quét nhanh không tạo contact sheets**:
  ```powershell
  python scripts/deduplicate_car_images.py --skip-contact-sheets
  ```

---

## 📊 4. Cấu Trúc Báo Cáo Được Sinh Ra

Toàn bộ báo cáo được lưu tại thư mục `reports/image_deduplication/`:

1. **`image_inventory.csv`**:
   Kiểm kê toàn bộ ảnh: `filename`, `relative_path`, `sha256`, `phash`, `width`, `height`, `file_size`, `readable`, `csv_reference_count`.
2. **`exact_duplicates.csv`**:
   Danh sách các nhóm trùng nhị phân: `group_id`, `image_path`, `preferred_image`, `sha256`, `csv_reference_count`.
3. **`near_duplicates_review.csv`**:
   Danh sách các cặp ảnh tương đồng trực giác: `group_id`, `image_path`, `candidate_preferred_image`, `phash_distance`, `review_status`, `reason`.
4. **`image_path_mapping_proposed.csv`**:
   Bảng đề xuất chuyển đổi đường dẫn: `old_image_path`, `proposed_image_path`, `duplicate_type`, `confidence_category`, `review_required`.
5. **`deduplication_summary.json`**:
   Thống kê số lượng quét, số nhóm trùng lặp, dung lượng tiết kiệm, thời gian chạy.
6. **`contact_sheets/`**:
   Thư mục chứa các ảnh `contact_sheet_XX.jpg` trình bày trực quan ảnh đại diện (Preferred) và ảnh ứng viên (Candidate) cùng độ phân giải, độ sắc nét và khoảng cách pHash.

---

## 📝 5. Quy Trình Xem Xét & Áp Dụng (Optional Apply)

Khi muốn áp dụng chuyển đổi đường dẫn sau khi đã rà soát:
1. Mở file `reports/image_deduplication/image_path_mapping_proposed.csv` hoặc các contact sheets để kiểm tra.
2. Các dòng có `review_required = False` (chủ yếu là Exact Duplicates) đã sẵn sàng được chuẩn hóa.
3. Chạy lệnh áp dụng an toàn:
   ```powershell
   python scripts/deduplicate_car_images.py --apply --confirm
   ```
4. Hệ thống sẽ:
   * Tạo bản sao dữ liệu mới: `data/vehicles_clean_dedup.csv` và `data/image_manifest_dedup.csv`.
   * Tạo tệp nhật ký kiểm toán: `reports/image_deduplication/apply_backup_manifest.json`.
   * **Giữ nguyên 100% hình ảnh và CSV gốc!**
