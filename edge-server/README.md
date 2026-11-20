# Smart Parking Edge Server (MySQL/InnoDB + FastAPI)

## Các thành phần chính (Phần việc của Việt)
- `migrations/001_mysql_tables.sql` & `002_mysql_foreign_keys.sql`: Schema MySQL/InnoDB 9 bảng chuẩn hóa, generated columns chống đặt trùng (`active_vehicle_booking`, `live_plate`, `active_user_id`), indexes và khóa ngoại.
- `src/smart_parking/infrastructure/security/embedding_cipher.py`: Mã hóa & giải mã vector khuôn mặt 512-D `float32` chuẩn hóa L2 bằng AES-256-GCM (`EmbeddingCipher`).
- `src/smart_parking/infrastructure/database/`: Bộ Repositories dùng `%s` parameterized queries + `UnitOfWork` với transaction ngắn, kiểm soát thứ tự khóa (`vehicles -> parking_slots -> bookings -> sessions -> gate_events`) và retry deadlock tự động.
- `src/smart_parking/application/services/`:
  - `AuthService`: Đăng nhập, xác thực JWT, phân quyền RBAC (`user` / `admin`).
  - `SlotService`: Tính toán trạng thái hiển thị tổng hợp 4 ô đỗ (`A1`, `A2`, `B1`, `B2`) và che giấu thông tin nhạy cảm theo role.
  - `BookingService`: Đặt giữ ô 60 phút, hủy đặt chỗ, đồng hồ đếm ngược theo `server_time`, worker xử lý hết hạn `expire_overdue_bookings`.
  - `GateDataService` (`SessionDataService`): Cổng tích hợp giao dịch ngắn cho luồng cổng vào/ra, cảm biến IR 4 ô và duyệt thủ công của Duy & Nam.
  - `RetentionService`: Xóa `session_face_templates` đã hết hạn của các phiên `Closed`/`Cancelled`.
- `scripts/init_database.py` & `scripts/seed_demo_data.py`: Khởi tạo MySQL schema và seed dữ liệu demo idempotent.
