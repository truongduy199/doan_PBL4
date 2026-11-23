# Reset dữ liệu lượt xe để test lại

Chạy PowerShell tại thư mục dự án. Xem trước, chưa thay đổi dữ liệu:

```powershell
.\scripts\reset_test_data.ps1
```

Reset sau khi xem đúng tên database và phạm vi:

```powershell
.\scripts\reset_test_data.ps1 -Apply
```

Script yêu cầu tắt nguồn cả hai ESP và bỏ vật che IR. Ngắt cả USB lẫn nguồn ngoài để xóa lượt/lệnh còn trong RAM bo. Script kiểm tra tiến trình đang giữ cổng backend, dừng đúng backend của ứng dụng, reset database trong một transaction rồi khởi động lại backend nếu trước đó đang chạy. Sau khi hoàn tất, cấp nguồn lại hai bo và tải lại dashboard. MySQL/Mosquitto vẫn giữ chạy. `-DevicesOffline` chỉ dùng khi đã thực sự ngắt nguồn hai bo; `-NoRestart` giữ backend dừng để bảo trì.

## Dữ liệu bị xóa

- Toàn bộ phiên vào/ra đang chạy và lịch sử (`sessions`).
- Mẫu mặt theo phiên (`session_face_templates`).
- Đặt chỗ (`bookings`), sự kiện/yêu cầu kiểm tra cổng (`gate_events`), nhật ký lượt thử (`parking_logs`).
- Gỡ liên kết đặt chỗ/phiên khỏi bốn ô. Trạng thái vật lý về `Unknown`, xóa boot/sequence/last_seen cũ; chờ IR thật báo lại, không tự gán `Free`.

## Dữ liệu được giữ

- Tài khoản, mật khẩu, quyền, trạng thái tài khoản (`users`).
- Xe đăng ký và liên kết chủ xe (`vehicles`).
- Mẫu mặt tài khoản (`user_face_templates`), giữ nguyên dữ liệu mã hóa.
- Mã ô/mã cảm biến A1–B2, cấu trúc database, model, firmware và cấu hình.

Không drop/truncate bảng, không tắt foreign key, không seed lại tài khoản. Nếu lỗi, các thay đổi database trong reset được rollback cùng nhau. Bộ đếm ID không bị đặt lại về 1. Nhật ký/sự kiện mới có thể xuất hiện lại khi hệ thống tiếp tục chạy.

## Đổi biển số USER thử nghiệm trong cùng lần reset

```powershell
.\scripts\reset_test_data.ps1 -DemoPlate 85H650346
.\scripts\reset_test_data.ps1 -Apply -DemoPlate 85H650346
```

Chỉ thay biển số của chiếc xe `Active` duy nhất thuộc `DEMO_USER_USERNAME`; không tạo/xóa xe hay thay mẫu mặt. Script từ chối nếu có nhiều xe để chọn, không tìm được tài khoản USER, hoặc biển số thuộc xe khác. Khi thành công, đồng bộ riêng `DEMO_VEHICLE_PLATE` trong `.env` cục bộ; các cấu hình khác giữ nguyên. Các lần reset sau không cần truyền `-DemoPlate` nữa.

Biển số trong database giữ cả chữ và số viết hoa, bỏ dấu gạch ngang, dấu chấm và khoảng trắng. Ví dụ `85-H6 503.46` được lưu là `85H650346`; chữ `H` và số `6` của sê-ri vẫn được giữ. Dashboard có thể định dạng lại để dễ đọc, không thay khóa lưu/đối chiếu.

Nếu dùng trực tiếp Python, mặc định cũng chỉ xem trước:

```powershell
.\.venv\Scripts\python.exe .\edge-server\scripts\reset_test_data.py
```

Chế độ Python `--apply` yêu cầu `--database` khớp đúng database trong cấu hình và backend đã dừng. Cách PowerShell ở trên thuận tiện hơn vì xử lý dừng/khởi động backend.
