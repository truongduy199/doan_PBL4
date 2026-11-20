# Từ Điển Dữ Liệu MySQL / InnoDB (Smart Parking PBL4 — Chốt 18/11/2026)

Hệ thống sử dụng **MySQL 8.0 / InnoDB** (`CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci`) làm nguồn chân lý duy nhất (Single Source of Truth) cho toàn bộ hệ thống Edge Server, Web User Đặt Chỗ 60 Phút và Admin Dashboard.

---

## 1. Quy Tắc Thời Gian, Thứ Tự Khóa & Tính Khả Dụng Ô Đỗ

1. **Múi giờ chuẩn:**
   - Mọi cột thời gian trong MySQL sử dụng kiểu `DATETIME(3)` lưu ở dạng **UTC (`+00:00`)**.
   - Tầng API trả kèm cả chuỗi ISO UTC (`...Z`) và giờ địa phương Việt Nam (`Asia/Ho_Chi_Minh`, `+07:00`).
2. **Công thức tính khả dụng của ô đỗ (`available(slot)`):**
   $$\text{available}(\text{slot}) = (\text{physical\_status} = \text{'Free'}) \land (\text{now\_utc} - \text{last\_seen\_at} \le \text{SLOT\_STALE\_SECONDS}) \land (\text{active\_booking\_id IS NULL}) \land (\text{reserved\_session\_id IS NULL})$$
   - Khởi tạo mặc định khi chưa có dữ liệu IR hợp lệ là `'Unknown'` (tuyệt đối không giả định `'Free'`).
   - Trong giai đoạn xe đặt trước đang làm thủ tục qua cổng vào (`Checkin_pending` / `Entry_pending`), `active_booking_id` và `reserved_session_id` cùng tồn tại trên đúng 1 ô. Khi xe thực sự qua cổng vào (`Active`), hệ thống xóa `active_booking_id = NULL` nhưng giữ `reserved_session_id = session_id`; lịch sử ô đã đặt vẫn bảo toàn trong `bookings.slot_id`.
3. **Thứ tự khóa dòng (`SELECT ... FOR UPDATE`) bắt buộc trong mọi giao dịch:**
   1. `vehicles` (Rank 1)
   2. `parking_slots` (Rank 2)
   3. `bookings` (Rank 3)
   4. `sessions` (Rank 4)
   5. `gate_events` (Rank 5)
   - Được kiểm soát tự động tại runtime bởi `LockOrderTracker` và tự động retry có giới hạn khi gặp InnoDB deadlock (`1213`) / lock wait timeout (`1205`).
   - Không bao giờ giữ transaction trong lúc chờ truyền ảnh camera, chạy suy luận AI hoặc chờ xe di chuyển qua barie.

---

## 2. Đặc Tả Chi Tiết 9 Bảng Dữ Liệu

### 2.1. Bảng `users`
Lưu thông tin tài khoản người dùng định danh (`user`) và quản trị viên (`admin`).
- `user_id` (`BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY`)
- `username` (`VARCHAR(100) NOT NULL UNIQUE`)
- `password_hash` (`VARCHAR(255) NOT NULL`) — Chỉ lưu mật khẩu đã băm (`bcrypt` / `PBKDF2`), không lưu plaintext.
- `display_name` (`VARCHAR(150) NULL`)
- `role` (`VARCHAR(20) NOT NULL`) — `'user' | 'admin'`
- `status` (`VARCHAR(20) NOT NULL`) — `'Active' | 'Disabled'`
- `created_at`, `updated_at` (`DATETIME(3) NOT NULL`)

### 2.2. Bảng `vehicles`
Lưu danh sách phương tiện định danh thuộc sở hữu của `users`.
- `vehicle_id` (`BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY`)
- `user_id` (`BIGINT UNSIGNED NOT NULL`, FK -> `users.user_id`)
- `plate_number` (`VARCHAR(20) NOT NULL UNIQUE`) — Biển số chuẩn hóa chữ hoa, bỏ khoảng trắng/dấu gạch/dấu chấm (ví dụ: `43A12345`).
- `status` (`VARCHAR(20) NOT NULL`) — `'Active' | 'Disabled'`
- `created_at`, `updated_at` (`DATETIME(3) NOT NULL`)

### 2.3. Bảng `user_face_templates`
Lưu mẫu khuôn mặt tham chiếu của chủ xe định danh phục vụ đối sánh 1:1 khi xe có đặt trước vào cổng.
- `template_id` (`BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY`)
- `user_id` (`BIGINT UNSIGNED NOT NULL`, FK -> `users.user_id`)
- `embedding_blob` (`BLOB NOT NULL`) — Vector 512 chiều `float32` chuẩn hóa L2 đã mã hóa AES-256-GCM qua `EmbeddingCipher`.
- `embedding_size` (`SMALLINT UNSIGNED NOT NULL DEFAULT 512`)
- `embedding_dtype` (`VARCHAR(20) NOT NULL DEFAULT 'float32'`)
- `model_id`, `model_version` (`VARCHAR(100) NOT NULL`), `config_version` (`VARCHAR(50) NOT NULL`)
- `quality_score` (`FLOAT NULL`)
- `liveness_status` (`VARCHAR(30) NOT NULL`) — `'Passed' | 'Failed' | 'Error' | 'Unavailable' | 'Not_used'` (Với mẫu nạp nội bộ không quét liveness trực tiếp phải ghi `'Not_used'`, `liveness_score = NULL`).
- `liveness_score` (`FLOAT NULL`)
- `key_version` (`VARCHAR(50) NOT NULL`), `encryption_metadata` (`JSON NOT NULL`)
- `status` (`VARCHAR(20) NOT NULL`) — `'Active' | 'Replaced' | 'Revoked'`
- `created_at` (`DATETIME(3) NOT NULL`), `revoked_at` (`DATETIME(3) NULL`)
- `active_user_id` (`BIGINT UNSIGNED GENERATED ALWAYS AS (CASE WHEN status = 'Active' THEN user_id ELSE NULL END) STORED UNIQUE`) — Đảm bảo mỗi `user_id` có tối đa 1 bản ghi `'Active'`.

### 2.4. Bảng `parking_slots`
Lưu trạng thái của 4 ô đỗ cố định (`A1`, `A2`, `B1`, `B2`).
- `slot_id` (`VARCHAR(10) PRIMARY KEY`) — `'A1' | 'A2' | 'B1' | 'B2'`
- `sensor_id` (`VARCHAR(50) NOT NULL UNIQUE`) — `'IR_A1' | 'IR_A2' | 'IR_B1' | 'IR_B2'`
- `physical_status` (`VARCHAR(20) NOT NULL DEFAULT 'Unknown'`) — `'Free' | 'Occupied' | 'Unknown' | 'Fault'`
- `active_booking_id` (`CHAR(36) NULL UNIQUE`, FK -> `bookings.booking_id`)
- `reserved_session_id` (`CHAR(36) NULL UNIQUE`, FK -> `sessions.session_id`)
- `last_boot_id` (`VARCHAR(64) NULL`), `last_sequence` (`BIGINT UNSIGNED NULL`), `last_seen_at` (`DATETIME(3) NULL`)
- `updated_at` (`DATETIME(3) NOT NULL`)

### 2.5. Bảng `bookings`
Lưu thông tin đặt giữ ô 60 phút và lịch sử đặt chỗ.
- `booking_id` (`CHAR(36) PRIMARY KEY`)
- `user_id` (`BIGINT UNSIGNED NOT NULL`, FK -> `users.user_id`)
- `vehicle_id` (`BIGINT UNSIGNED NOT NULL`, FK -> `vehicles.vehicle_id`)
- `slot_id` (`VARCHAR(10) NOT NULL`, FK -> `parking_slots.slot_id`) — Không đặt UNIQUE trên `slot_id` để lưu lịch sử.
- `status` (`VARCHAR(30) NOT NULL`) — `'Reserved' | 'Checkin_pending' | 'Checked_in' | 'Completed' | 'Expired' | 'Cancelled'`
- `created_at`, `expires_at` (`DATETIME(3) NOT NULL`)
- `checkin_started_at`, `checked_in_at`, `completed_at`, `cancelled_at` (`DATETIME(3) NULL`)
- `checkin_event_id` (`CHAR(36) NULL`, FK -> `gate_events.event_id`)
- `active_vehicle_booking` (`BIGINT UNSIGNED GENERATED ALWAYS AS (CASE WHEN status IN ('Reserved', 'Checkin_pending') THEN vehicle_id ELSE NULL END) STORED UNIQUE`) — Chống 1 xe tạo 2 booking hoạt động cùng lúc.
- Indexes: `idx_bookings_status_expires (status, expires_at)`, `idx_bookings_vehicle_status (vehicle_id, status)`, `idx_bookings_user_created (user_id, created_at)`.

### 2.6. Bảng `sessions`
Lưu thông tin phiên gửi xe thực tế (cả xe đặt trước và khách vãng lai).
- `session_id` (`CHAR(36) PRIMARY KEY`)
- `plate_number` (`VARCHAR(20) NOT NULL`)
- `user_id` (`BIGINT UNSIGNED NULL`), `vehicle_id` (`BIGINT UNSIGNED NULL`), `booking_id` (`CHAR(36) NULL UNIQUE`)
- `assigned_slot_id` (`VARCHAR(10) NOT NULL`, FK -> `parking_slots.slot_id`)
- `status` (`VARCHAR(30) NOT NULL`) — `'Entry_pending' | 'Active' | 'Exit_pending' | 'Closed' | 'Cancelled'`
- `parking_status` (`VARCHAR(40) NOT NULL`) — `'Not_arrived' | 'Parking_pending' | 'Parked_confirmed' | 'Parking_review_required' | 'Parking_timeout'`
- `ocr_confidence` (`FLOAT NULL`)
- `entry_time`, `exit_time` (`DATETIME(3) NULL`)
- `created_at`, `updated_at` (`DATETIME(3) NOT NULL`)
- `live_plate` (`VARCHAR(20) GENERATED ALWAYS AS (CASE WHEN status IN ('Entry_pending', 'Active', 'Exit_pending') THEN plate_number ELSE NULL END) STORED UNIQUE`) — Chống 2 phiên chưa kết thúc cho cùng biển số.
- Index: `idx_sessions_plate_status (plate_number, status)`.

### 2.7. Bảng `session_face_templates`
Lưu mẫu khuôn mặt chụp tại cổng vào của từng phiên (`sessions`) để đối sánh 1:1 tại cổng ra.
- `template_id` (`BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY`)
- `session_id` (`CHAR(36) NOT NULL UNIQUE`, FK -> `sessions.session_id`)
- `embedding_blob` (`BLOB NOT NULL`), `embedding_size` (`512`), `embedding_dtype` (`'float32'`)
- `model_id`, `model_version`, `config_version`, `quality_score`, `liveness_status`, `liveness_score`, `key_version`, `encryption_metadata`
- `captured_at` (`DATETIME(3) NOT NULL`), `expires_at` (`DATETIME(3) NULL`)

### 2.8. Bảng `gate_events`
Lưu các sự kiện quyết định và di chuyển qua cổng vào (`IN`) / cổng ra (`OUT`) cùng lịch sử duyệt ngoại lệ (`Manual Review`).
- `event_id` (`CHAR(36) PRIMARY KEY`)
- `gate_id` (`'IN' | 'OUT'`), `device_id` (`VARCHAR(50) NOT NULL`)
- `session_id` (`CHAR(36) NULL`), `booking_id` (`CHAR(36) NULL`)
- `decision` (`'Pending' | 'Approved' | 'Denied' | 'Review_required'`)
- `passage_status` (`'Waiting' | 'Confirmed' | 'Cancelled' | 'Unknown'`)
- `reason_code`, `liveness_status`, `liveness_score`, `liveness_model_version`, `face_config_version`, `command_id`
- `reviewer_id` (`BIGINT UNSIGNED NULL`, FK -> `users.user_id`), `review_reason` (`TEXT NULL`)
- `created_at`, `decided_at`, `passed_at` (`DATETIME(3)`)
- Index: `idx_gate_events_session_created (session_id, created_at)`.

### 2.9. Bảng `parking_logs`
Bảng nhật ký kiểm toán (Audit Log) toàn hệ thống.
- `log_id` (`BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY`)
- `event_id` (`CHAR(36) NULL`), `session_id` (`CHAR(36) NULL`), `actor_user_id` (`BIGINT UNSIGNED NULL`)
- `event_type` (`VARCHAR(50) NOT NULL`), `reason_code` (`VARCHAR(60) NOT NULL`)
- `details` (`JSON NULL`) — Đã lọc bỏ tự động mật khẩu, khóa bí mật và vector khuôn mặt qua `sanitize_log_details`.
- `created_at` (`DATETIME(3) NOT NULL`)
- Index: `idx_parking_logs_session_created (session_id, created_at)`.
