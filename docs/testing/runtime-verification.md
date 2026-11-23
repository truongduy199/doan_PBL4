# Kết quả kiểm tra tích hợp phần mềm

## Chuyển sang MJPEG - 23/11/2026

- Hai bo đã build/nạp và xác minh hash; heartbeat của COM5/COM6 báo `stream_transport=mjpeg`. Cả backend và dashboard đã cập nhật. Ảnh AI vẫn chụp và gửi riêng qua `/api/device/images`; kiểm tra chụp tĩnh sau stream nhận được ảnh mới từ cả hai camera.
- ESP gửi multipart JPEG trên một HTTP POST chunked giữ kết nối tới backend. Dashboard mở hai HTTP GET MJPEG có xác thực quản trị, không nhận JPEG Base64 qua polling. Metadata cập nhật mỗi giây; chỉ giữ khung mới nhất trong RAM, không lưu video/ảnh xuống đĩa.
- Đo tại endpoint xem MJPEG thật, hai camera đồng thời: biển số **59 khung/12,16 giây = 4,85 FPS**; khuôn mặt **57 khung/12,28 giây = 4,64 FPS**. Nội dung của tất cả các khung trong mẫu đều khác nhau, JPEG giải mã được. Đây là tốc độ tại đầu xem HTTP, chưa phải phép đo tốc độ vẽ màn hình trình duyệt.
- IR OUT đang hiện diện đã tự kích hoạt MJPEG. Sau khi người dùng bỏ vật che, lượt chuyển `CANCELLED`, hai cổng về `Idle`, hai bo báo `streaming=false` và backend kết thúc luồng. Lượt đầu sau nạp trả `CAPTURE_TIMEOUT`; đợt kiểm tra này chưa đánh giá việc nhận diện AI thành công.
- Xem kiểm tra 30 giây: hai HTTP GET đều tự đóng sau **30,03 giây** với boundary kết thúc hợp lệ; heartbeat sau đó của cả hai bo báo ngừng phát. Không mở cổng thủ công khi đo.
- Bộ backend và mô-đun biển số: **64 passed**, dùng DB kiểm thử trong RAM. Có thêm kiểm tra multipart bị chia tại mọi vị trí byte, dữ liệu quá lớn/bị cắt, khóa sai, mã luồng cũ, quyền ADMIN/USER, ảnh JPEG và response MJPEG. Hai firmware và TypeScript/Vite build đạt.

## Kiểm tra stream trên hai bo thật - 23/11/2026

- Sau phản hồi ảnh đảo ngược, thêm `CAMERA_ROTATE_180=1` vào firmware, đảo đồng thời hai trục tại cảm biến. Hai môi trường build đạt; đã nạp và xác minh hash trên COM5/COM6. Sau khởi động lại, cả hai camera báo sẵn sàng và gửi được JPEG mới theo đúng mã chụp kiểm tra. Ảnh biển số đã đúng chiều; camera khuôn mặt lúc chụp đang hướng lên trần nên chưa xác nhận trực quan chiều khuôn mặt người. Ảnh kiểm tra chỉ xử lý trong RAM.
- Bo khuôn mặt COM5 và bo biển số/điều khiển COM6 đều online, camera sẵn sàng, hỗ trợ stream; bo điều khiển báo OLED sẵn sàng. Không nạp lại firmware trong lượt kiểm tra này.
- Kiểm tra xem trực tiếp qua API quản trị: trong 12 giây nhận 24 JPEG từ mỗi bo, khoảng 2 khung/giây mỗi camera. POST ảnh từ bo điều khiển trả HTTP 200.
- Kiểm tra phiên xem 30 giây: nhận ít nhất 51 khung biển số và 43 khung khuôn mặt; các mẫu lấy mỗi 2 giây có 15/12 nội dung JPEG khác nhau, xác nhận ảnh thay đổi. Backend tự kết thúc phiên; heartbeat sau đó của cả hai bo báo `streaming=false`. Tốc độ có dao động, không phải cam kết FPS liên tục.
- Người dùng đưa xe/vật tới IR IN thật: backend tự tạo luồng theo lượt xe (không phải preview). Bộ đếm ghi nhận ít nhất 74 khung biển số và 89 khung khuôn mặt. Khi người dùng đưa xe ra, lượt chuyển `CANCELLED`, luồng ngừng, hai bo báo `streaming=false`, cổng IN trở lại `Idle` và xóa event hiện hành.
- Lượt IR thử trả `INVALID_PLATE_FORMAT`; chưa chứng minh nhận diện biển số/khuôn mặt thành công hoặc xe qua barie. Không phát lệnh mở cổng thủ công trong kiểm tra này.
- Kiểm tra qua backend/API và log USB thật; công cụ truy cập Chrome lỗi nên chưa xác minh trực quan hai khung trên trình duyệt trong lượt này. Không lưu JPEG/khuôn mặt xuống đĩa; file chẩn đoán cục bộ chỉ ghi mã lượt, số khung và trạng thái dừng.
- Trước lượt kiểm tra phần cứng, bộ backend và mô-đun biển số đã đạt **59 passed** với DB kiểm thử trong RAM; firmware của hai môi trường và dashboard TypeScript/Vite đã build thành công. Các mục bên dưới là kết quả lịch sử tại thời điểm ghi, không phản ánh giới hạn môi trường hiện tại.

## Kiểm tra sau dọn source - 22/11/2026

- Đã loại 62 file nguồn dư thừa: Firebase runtime/rules/contracts và script thử cũ, AI đếm ô đỗ, workflow rỗng, sketch test chưa triển khai, kịch bản không có runner, khung đánh giá, ba fake rỗng, các file frontend dư và ba class khung biển số.
- Giữ test nghiệp vụ, `fake_mysql_db.py`, `dashboard/spa.py`, model và các cấu hình cục bộ. Sáu file mang tên người đã được đổi sang tên chức năng; lệnh và liên kết liên quan đã cập nhật.
- Toàn bộ `edge-server/tests` và `modules/license_plate_yolo_numpy/tests`: **49 passed**. Bộ acceptance được ép dùng database trong RAM bằng `SystemAcceptanceTests._use_real_mysql = False`; không khởi tạo hoặc xóa database MySQL demo.
- `npm run build` trong `dashboard/`: TypeScript và Vite build đạt. Đây là kiểm tra build, chưa phải kiểm thử thao tác giao diện trên trình duyệt.
- `scripts/check_environment.py --runtime --network`: 0 vấn đề; MySQL và MQTT chấp nhận kết nối TCP. JSON contracts hợp lệ, không còn import `smart_parking` trỏ đến module đã xóa; các liên kết tài liệu vừa sửa hợp lệ.
- Đã sửa một test tích hợp cũ để gửi đủ `vehicle_id` theo API đặt chỗ. Kiểm tra frontend trong bộ acceptance hỗ trợ cả bản Vite và giao diện dự phòng.
- Bộ test vẫn phát cảnh báo về phiên bản Starlette/httpx và khóa JWT dành riêng cho test. Không có test thất bại. Chưa chạy kiểm thử Vitest frontend trong đợt này.

Các kết quả này không chứng minh độ chính xác AI, liveness hoặc phần cứng thật. Đợt dọn dẹp không nạp bo, thay đổi `.env`/`config.local.h` hoặc dừng backend/broker.

## Lịch sử kiểm tra - 21/11/2026

| Phạm vi | Kết quả | Giới hạn |
| --- | --- | --- |
| `test_gate_runtime.py` | 17/17 đạt | Repository thật, DB kiểm thử cô lập, AI được tiêm kết quả; kiểm tra ảnh dùng decoder giả để kiểm tra giao thức. |
| `test_system_acceptance.py` | 14 đạt, 1 bỏ qua | Dùng DB kiểm thử tương thích MySQL trên SQLite trong môi trường này. Bài phục vụ frontend bỏ qua vì thiếu FastAPI/uvicorn. |
| Phân tích cú pháp Python | 166 file, không lỗi cú pháp | Không thay cho import và chạy các thư viện native. |
| `scripts/check_environment.py` | Không phát hiện lỗi nguồn/JSON | Chế độ không có `--runtime` chỉ kiểm tra mã nguồn và JSON. |
| `scripts/check_contracts.py` | 10 file JSON đọc được | Chỉ kiểm tra cú pháp JSON, không chứng minh payload thiết bị tuân thủ mọi schema. |
| Script khởi động PowerShell | Cú pháp hợp lệ | Chưa khởi động dịch vụ thật. |
| PlatformIO | Có ba môi trường cấu hình | Chưa biên dịch toolchain ESP32. |

17 bài kiểm thử tích hợp luồng cổng bao gồm luồng walk-in vào/đỗ/ra, tạo phiên trước khi duyệt booking, không mở lặp, tách ACK với passage, timeout chụp, hủy lượt khi xe rời trong lúc AI, lỗi database, mất broker, xác thực HTTP thiết bị, metadata/ROI/frame, ảnh trùng/quá hạn, snapshot boot cũ, khôi phục xác nhận passage sau backend restart và thiếu model không tự tải/giả lập thành công.

Bài nghiệm thu manual review cũ được cập nhật: APPROVE một event lưu trong DB nhưng không còn lượt thiết bị phải trả 409; DENY vẫn ghi audit và không mở cổng. Không giữ kỳ vọng cũ cho phép mở cổng chỉ từ một bản ghi review cũ.

## Chưa chạy được trong môi trường thực hiện

- Bộ pytest/OpenCV và HTTP FastAPI thật: thiếu thư viện cần thiết; thử tải bằng pip không thành công do không phân giải được địa chỉ máy chủ gói.
- Build/type-check Vite/React: chưa có `dashboard/node_modules` và npm trong PATH môi trường. Đã tách `src/test` khỏi build sản phẩm để phần kiểm thử Vitest không chặn build giao diện.
- Biên dịch firmware bằng PlatformIO/Arduino, kết nối Mosquitto/MySQL thật, mDNS thật và suy luận model thật.
- Nạp hai S3, kiểm tra camera/PSRAM/IR/servo/OLED/còi/nguồn, thời gian vòng điều khiển, độ trễ và demo có xe thật.

Không dùng các kết quả trên để công bố độ chính xác AI, FPS, độ trễ GPIO hay hiệu năng InnoDB. Chưa thực hiện thao tác xóa dữ liệu demo, cài broker thành service, đổi mạng/firewall hoặc nạp firmware lên thiết bị.

## Tệp cần dùng khi ghép hệ thống

- [Cấu hình và trình tự triển khai](../setup/system-integration.md)
- [Hợp đồng HTTP/MQTT](../protocols/mqtt-http-device-contract.md)
- [Bảng chân và nguồn](../setup/hardware-wiring.md)
- [Môi trường build firmware](../../firmware/platformio.ini)
- [Kiểm tra trước khi chạy](../../scripts/check_environment.py)
- [Khởi động backend](../../scripts/start_backend.ps1)
