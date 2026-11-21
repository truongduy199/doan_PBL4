# Kết quả kiểm tra phần mềm Duy - 21/11/2026

## Đã chạy

| Phạm vi | Kết quả | Giới hạn |
| --- | --- | --- |
| `test_duy_runtime.py` | 17/17 đạt | Repository thật, DB kiểm thử cô lập, AI được tiêm kết quả; kiểm tra ảnh dùng decoder giả để kiểm tra giao thức. |
| `test_viet_acceptance_suite.py` | 14 đạt, 1 bỏ qua | Dùng DB kiểm thử tương thích MySQL trên SQLite trong môi trường này. Bài phục vụ frontend bỏ qua vì thiếu FastAPI/uvicorn. |
| Phân tích cú pháp Python | 166 file, không lỗi cú pháp | Không thay cho import và chạy các thư viện native. |
| `scripts/check_duy.py` | Không phát hiện lỗi nguồn/JSON | Chế độ không có `--runtime` chỉ kiểm tra mã nguồn và JSON. |
| `scripts/check_contracts.py` | 10 file JSON đọc được | Chỉ kiểm tra cú pháp JSON, không chứng minh payload thiết bị tuân thủ mọi schema. |
| Script khởi động PowerShell | Cú pháp hợp lệ | Chưa khởi động dịch vụ thật. |
| PlatformIO | Có ba môi trường cấu hình | Chưa biên dịch toolchain ESP32. |

17 bài riêng của Duy bao gồm luồng walk-in vào/đỗ/ra, tạo phiên trước khi duyệt booking, không mở lặp, tách ACK với passage, timeout chụp, hủy lượt khi xe rời trong lúc AI, lỗi database, mất broker, xác thực HTTP thiết bị, metadata/ROI/frame, ảnh trùng/quá hạn, snapshot boot cũ, khôi phục xác nhận passage sau backend restart và thiếu model không tự tải/giả lập thành công.

Bài nghiệm thu manual review cũ được cập nhật: APPROVE một event lưu trong DB nhưng không còn lượt thiết bị phải trả 409; DENY vẫn ghi audit và không mở cổng. Không giữ kỳ vọng cũ cho phép mở cổng chỉ từ một bản ghi review cũ.

## Chưa chạy được trong môi trường thực hiện

- Bộ pytest/OpenCV và HTTP FastAPI thật: thiếu thư viện cần thiết; thử tải bằng pip không thành công do không phân giải được địa chỉ máy chủ gói.
- Build/type-check Vite/React: chưa có `dashboard/node_modules` và npm trong PATH môi trường. Đã tách `src/test` khỏi build sản phẩm để phần kiểm thử Vitest không chặn build giao diện.
- Biên dịch firmware bằng PlatformIO/Arduino, kết nối Mosquitto/MySQL thật, mDNS thật và suy luận model thật.
- Nạp hai S3, kiểm tra camera/PSRAM/IR/servo/OLED/còi/nguồn, thời gian vòng điều khiển, độ trễ và demo có xe thật.

Không dùng các kết quả trên để công bố độ chính xác AI, FPS, độ trễ GPIO hay hiệu năng InnoDB. Chưa thực hiện thao tác xóa dữ liệu demo, cài broker thành service, đổi mạng/firewall hoặc nạp firmware lên thiết bị.

## Tệp cần dùng khi ghép hệ thống

- [Cấu hình và trình tự triển khai](../setup/duy-handover.md)
- [Hợp đồng HTTP/MQTT](../protocols/mqtt-http-device-contract.md)
- [Bảng chân và nguồn](../setup/hardware-wiring.md)
- [Môi trường build firmware](../../firmware/platformio.ini)
- [Kiểm tra trước khi chạy](../../scripts/check_duy.py)
- [Khởi động backend](../../scripts/start_duy.ps1)
