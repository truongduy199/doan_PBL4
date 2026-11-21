# Kết quả kiểm thử ngày 20/11/2026

Môi trường Windows với Python 3.10.11, Ultralytics 8.4.216, PyTorch 2.14.1 và NumPy 2.2.6.

- `python -m pytest -q` đạt **5/5**. Các bài kiểm thử dùng detector giả lập để xác nhận cắt ảnh BGR, nhận nhiều vùng biển số, nạp mô hình một lần và lưu ảnh qua CLI. OCR sử dụng trọng số thật.
- `python -m build --no-isolation` tạo được bản mã nguồn và wheel. Cài wheel vào môi trường ảo, import từ ngoài thư mục mã nguồn và xác nhận cả hai tệp trọng số đã được cài theo gói. `python -m pip check` báo các phụ thuộc hợp lệ.
- CLI từ wheel chạy với **YOLO và OCR thật** trên `samples/synthetic_plate.png`, phát hiện **1 biển số**, bbox `(35, 46, 398, 169)`, điểm YOLO `0.5606`, OCR `43A12345` và 8 ký tự. CLI lưu ảnh đã đánh dấu vào `results/wheel-smoke.png`.
- `python main.py --help` hiển thị các tùy chọn. Đường dẫn ảnh không tồn tại trả thông báo lỗi và mã thoát `1`.

Độ chính xác trên ảnh xe thật và luồng camera tại bãi đỗ xe chưa được đo.
