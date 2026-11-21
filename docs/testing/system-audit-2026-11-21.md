# Kiểm tra AI, database và UI - 21/11/2026

## Phạm vi và kết luận

Đã kiểm tra mã nguồn hiện có và sửa giao diện `/login`, `/user`, `/admin`. Chưa đủ điều kiện kết luận toàn hệ thống hoặc toàn bộ UI đã chạy end-to-end trên máy thật: môi trường thực hiện thiếu phụ thuộc runtime và không được truy cập các cổng localhost. MySQL/broker/camera thực tế chưa được xác minh; điều này không có nghĩa các dịch vụ đó chắc chắn đang tắt.

## AI

| Thành phần | Kết quả thực hiện |
| --- | --- |
| YOLO biển số | Có `best.pt`, 6.252.906 byte; archive CRC hợp lệ. Chưa chạy suy luận YOLO vì thiếu PyTorch/Ultralytics/OpenCV trong môi trường. |
| OCR NumPy | Có `ocr_coco_weights.npz`, 4.027.326 byte. Các tensor đúng shape, hữu hạn. Nạp trọng số thật và chạy forward trên 2 đầu vào; trả 36 xác suất mỗi đầu vào, tổng xấp xỉ 1. Đây không phải bài đo độ chính xác nhận diện biển số. |
| SCRFD / ArcFace | Chưa có các model ONNX cần thiết trong thư mục Buffalo-L của repo. Không chạy được suy luận khuôn mặt thật. |
| Liveness | Chưa có `addons/liveness.onnx`; cũng chưa xác minh bản InsightFace/addon tương thích của Nam. Không tự thay bằng trạng thái Passed. |
| Đánh giá | Các script trong `evaluation/` hiện là khung chú thích, chưa tạo kết quả đánh giá. Không có bằng chứng đo TAR/FAR/accuracy/latency độc lập để công bố. |

Đã thay script hash chỉ in thông báo bằng kiểm tra SHA256, CRC và forward OCR thật. Manifest tại `contracts/models.sha256.json` ghi nhận trọng số hiện có; nó phát hiện thay đổi tệp, không chứng nhận nguồn train hoặc chất lượng model. Kiểm tra bằng `python edge-server/scripts/verify_model_hashes.py`; thêm `--require-face` để báo lỗi khi thiếu tài nguyên mặt/liveness.

`download_insightface_models.py` hiện vẫn là placeholder; không dùng thông báo của script đó để kết luận đã tải model.

## Database và backend

Đã đối chiếu schema 9 bảng, khóa ngoại, generated columns chống trùng booking/phiên, trạng thái phiên/ô, mã hóa embedding và luồng vào/ra bằng repository/service thật với database kiểm thử cô lập.

Các sửa chữa cụ thể:

- Backend giới hạn `event_id` 36 ký tự cho khớp MySQL `CHAR(36)`; firmware dùng phần millis/counter dạng hex có độ dài cố định, không tăng độ dài vượt cột theo thời gian. `command_id` vượt giới hạn bị từ chối.
- Không tiếp tục mã hóa embedding bằng thuật toán dự phòng trong khi gắn nhãn AES-256-GCM. Thiếu `cryptography` thì dừng mã hóa mới; vẫn giữ đường đọc tương thích các bản ghi cũ có metadata `builtin-aead`. Bản ghi AES bị sửa byte phải bị từ chối.
- Thêm timeout kết nối MySQL, tránh chờ kết nối vô hạn trong luồng tải UI.

Đã chạy 18 bài điều phối, 3 bài mã hóa và 15 bài acceptance: **35 bài đạt, 1 bài bỏ qua** vì thiếu FastAPI/uvicorn cho kiểm tra phục vụ trang. Database trong các kiểm thử là SQLite tương thích SQL phục vụ kiểm thử, không chứng minh hành vi lock/deadlock của InnoDB thật. Chưa có thao tác seed, reset hoặc sửa database demo thực tế.

## Giao diện

Đã dùng chung AppShell, logo chữ P, Notice, StatusBadge, ParkingFloorPlan, SummaryStat và ConfirmDialog. Font hệ thống, nền xám ấm, xanh trầm, viền mảnh; bỏ gradient/emoji trên màn hình nghiệp vụ, giảm nhãn kỹ thuật và tiêu đề quảng cáo. Các thành phần camera/benchmark cũ không còn hiển thị 3 camera, hình giả hoặc số chính xác/độ trễ không có chứng cứ.

Giữ chức năng: chọn ô, đặt/hủy, đếm ngược, theo dõi lượt gửi xe, lịch sử, mô phỏng bốn tuyến, giám sát quản trị, review có lý do, thiết bị và audit log. Đã sửa việc tự bật mô phỏng sau đặt chỗ; người dùng mở bằng nút riêng. Thêm polling cho User, không gửi lại request hết hạn mỗi giây, và xử lý thoát UI cả khi máy chủ không xác nhận đăng xuất; trường hợp đó có thông báo rõ.

Đã chuyển đổi biên dịch **32 tệp TS/TSX và bản ghép SPA** bằng Babel. Đã thực thi mã API client để kiểm tra URL cùng origin, URL Vite, cấu hình URL riêng, Bearer/credentials, lỗi 409, xóa token khi logout lỗi, chuyển WebSocket sang SSE/cleanup với transport giả lập, và vị trí cuối của cả bốn tuyến mô phỏng. Đây không phải TypeScript type-check đầy đủ, Vite production build hay React browser test.

Đã thử dựng `scripts/run_ui_sandbox.py`, dùng service/repository thật với DB trong RAM và không nối thiết bị. Trang có banner nhận diện dữ liệu kiểm thử. Tiến trình khởi động được nhưng trình duyệt không truy cập được cổng 8765; kiểm tra TCP trong môi trường trả PermissionError cho 3306/1883/8000/8765. Mở bản HTML bằng giao thức file cũng bị chính sách trình duyệt chặn. Không tiếp tục bằng cách vượt chính sách và không có ảnh chụp giao diện được xác nhận.

Chưa xác nhận trực quan desktop/mobile, bố cục sau render, thao tác bấm thực tế, WebSocket/SSE thật hoặc lỗi console của React. Cần chạy trên máy có quyền truy cập localhost để hoàn tất.

## Kiểm tra tiếp trên máy có môi trường đầy đủ

1. Cài phụ thuộc backend và đúng bộ InsightFace/addon của Nam; nạp Buffalo-L và liveness thật.
2. Kiểm tra kết nối MySQL/broker và cấu hình `.env`, không reset dữ liệu demo.
3. Trong `dashboard`, chạy `npm install` rồi `npm run build`; backend ưu tiên bản dist.
4. Khởi động backend, mở `/login`, kiểm tra cả USER/ADMIN, đặt/hủy/đếm ngược/lịch sử/review, desktop/mobile và mất kết nối.
5. Chạy riêng suy luận YOLO, OCR trên ảnh biển thật, đối sánh/liveness trên dữ liệu độc lập và ghi kết quả.

Script `npm test` hiện tham chiếu Vitest nhưng manifest chưa khai báo Vitest; cần bổ sung phụ thuộc kiểm thử khi chuẩn bị môi trường frontend test. Không nhầm với kết quả chuyển đổi mã đã chạy ở trên.

Quy ước style: [ui-style-guide.md](../ui-style-guide.md). Triển khai phần cổng: [duy-handover.md](../setup/duy-handover.md).
