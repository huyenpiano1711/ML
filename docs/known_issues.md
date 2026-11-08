# Lỗi còn tồn tại

Danh sách các lỗi từ đợt kiểm thử (sheet test, 06/11/2026) chưa sửa hoặc mới sửa một phần sau commit `0fab0e8`.
Những lỗi còn lại trong đợt kiểm thử đã được sửa và có test trong `tests/test_input_rules.py`.

| # | Lỗi | Trạng thái | Lý do / việc cần làm |
|---|---|---|---|
| 1 | Ảnh không đúng xe (ví dụ `ford_f150_2018.jpg` là ảnh khung gầm, `ford_f150_2016.jpg` là xe mô hình đồ chơi). | Đã xử lý một phần (07/11/2026) | Đã xóa 269 ảnh sai khỏi `assets/car_images_unique` (danh sách trong `assets/removed_images.csv`) và bỏ 6.329 xe dùng các ảnh đó khỏi catalog gợi ý (còn 184.867 xe); mô hình giá không đổi. Ảnh `ford_f150_2016.jpg` chưa bị xóa. Các ảnh còn lại chưa được rà hết bằng mắt. |
| 2 | Khi mở app mà mô hình hoặc thư viện bị lỗi, nút ANALYZE vẫn bấm được. | Sửa một phần | Hộp thoại "AutoWise could not load everything" đã hiện ngay khi mở app và ghi rõ thư viện nào sai. Nút ANALYZE được giữ lại có chủ ý: khi mô hình giá lỗi, Backend vẫn gợi ý được Top 5 xe và xe cùng tầm giá. |
| 3 | Số giá ước tính trên trang kết quả hiện chữ quá nhỏ. | Không tái hiện được | Khi dựng lại trang kết quả (Ford F150 2018), số "$34,974" hiện cỡ 48px, to hơn dòng "Likely price" (trước đây là "Reference range"). Cần chụp lại màn hình trên máy gặp lỗi (có thể do thiếu font Playfair Display hoặc ảnh chụp lúc chưa nạp stylesheet). |
| 4 | `tests/test_environment_and_sweep.py` của sheet test (kiểm tra môi trường, quét 107 loại xe) chưa có trong repo. | Chưa đưa vào repo | Người viết sheet cần gửi file này để đưa vào `tests/`. Phần kiểm tra phiên bản thư viện đã có trong `test_input_rules.py`. |

## Những chỗ chọn khác đề xuất của sheet test

Các test trong sheet có thể cần sửa cho khớp:

- Số dặm vô lý (quá 50.000 dặm cho mỗi năm tuổi xe, hoặc xe "New" quá 10.000 dặm) bị **chặn** khi bấm ANALYZE, không chỉ cảnh báo.
- `requirements.txt` ghi `pandas>=2.3` thay vì `pandas>=3.0`: pandas 2.3.3 nạp được mô hình và catalog và cho cùng giá dự đoán, còn pandas 2.2 thì lỗi. `numpy>=2.0` đúng như đề xuất.
- Tài khoản tạo trước khi đổi quy tắc mật khẩu (ví dụ mật khẩu `123456`) vẫn đăng nhập được; quy tắc mới chỉ áp dụng khi đăng ký.
