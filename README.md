# Hệ Thống Bãi Đỗ Xe Thông Minh IoT (PBL4 — Smart Parking System)

> **Tích hợp hệ thống (21/11/2026):** firmware hai ESP32-S3 dùng Wi-Fi HTTP/MQTT, không còn DevKit/Serial trong vận hành. Xem [hướng dẫn cấu hình, build và chạy](docs/setup/system-integration.md), [hợp đồng thiết bị](docs/protocols/mqtt-http-device-contract.md) và [bảng chân mới](docs/setup/hardware-wiring.md). Broker, model AI và thông tin mạng phải được cấu hình trước khi demo thật.

Kiến trúc hệ thống đã chốt ngày **18/11/2026**:
- **MySQL 8.0 / InnoDB** duy nhất trên laptop làm nguồn chân lý dữ liệu (Single Source of Truth) cho toàn bộ 9 bảng nghiệp vụ (`users`, `vehicles`, `user_face_templates`, `parking_slots`, `bookings`, `sessions`, `session_face_templates`, `gate_events`, `parking_logs`).
- **FastAPI REST & Realtime API (WebSocket `/api/ws` & SSE `/api/events/stream`)** tại `edge-server/`.
- **Web User (`/user`) & Admin Dashboard (`/admin`)** xây dựng bằng **React + TypeScript + Vite + Tailwind CSS** tại `dashboard/` (đã loại bỏ hoàn toàn Firebase và dữ liệu mock giả trong luồng vận hành).
- **Đặt giữ ô đỗ 60 phút** với đồng hồ đếm ngược đồng bộ theo `server_time` / `expires_at` của server và **Mô phỏng đường đi góc nhìn thứ nhất từ sau vô lăng (First-Person Driver Cockpit View)** cho cả 4 tuyến ô `A1`, `A2`, `B1`, `B2`.

---

## 1. Hướng Dẫn Khởi Tạo MySQL Local, Migrations & Seed Dữ Liệu Demo

### Bước 1.1: Cấu hình biến môi trường (`.env`)
Sao chép file cấu hình mẫu tại `edge-server/.env.example` thành `edge-server/.env`:
```powershell
cd c:\PBL4\doan_PBL4\edge-server
Copy-Item .env.example .env
```
Kiểm tra các thông số kết nối MySQL và khóa mã hóa trong `edge-server/.env`:
```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=smart_parking_pbl4

# Khóa mã hóa AES-256-GCM cho vector khuôn mặt 512-D (luôn giữ ngoài database)
EMBEDDING_SECRET_KEY=MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=
EMBEDDING_KEY_VERSION=v1
JWT_SECRET_KEY=pbl4_smart_parking_jwt_secret_key_2026_change_in_prod
```

### Bước 1.2: Chạy Migrations khởi tạo 9 bảng MySQL / InnoDB
Script `init_database.py` tự động tạo database `smart_parking_pbl4` (`utf8mb4_unicode_ci`) và chạy toàn bộ các file SQL trong `edge-server/migrations/` (`001_mysql_tables.sql`, `002_mysql_foreign_keys.sql`) một cách idempotent:
```powershell
cd c:\PBL4\doan_PBL4\edge-server
python scripts/init_database.py
```

### Bước 1.3: Seed Tài Khoản Demo, Xe Định Danh, 4 Ô Đỗ & Mẫu Khuôn Mặt Tài Xế
1. **Chế độ chuẩn bị nhanh cho buổi Demo (kèm sẵn 4 ô `A1`–`B2`, 1 ADMIN, 1 USER demo `viet_user`, 1 xe `43A12345`, 1 mẫu khuôn mặt 512-D mã hóa BLOB và bộ test fixtures):**
   ```powershell
   python scripts/seed_demo_data.py --with-test-fixtures --init-slots-free
   ```
   - Tài khoản **USER demo**: `username = viet_user` / `password = Viet@123` (Xe định danh: `43A12345`, hiển thị `43A-123.45`).
   - Tài khoản **ADMIN**: `username = admin` / `password = Admin@123`.

2. **Chế độ tích hợp vector 512-D thực tế từ công cụ trích xuất Buffalo-L của Nam:**
   Khi Nam xuất file JSON/NPY chứa vector 512-D `float32` chuẩn hóa L2 của tài xế demo (hoặc nạp từ ảnh mẫu), chạy lệnh sau để mã hóa bằng `EmbeddingCipher` và cập nhật vào `user_face_templates` (mẫu `Active` cũ sẽ tự động chuyển sang `'Replaced'` kèm `revoked_at` trong cùng 1 transaction, và ghi đúng `liveness_status = 'Not_used'`, `liveness_score = NULL`):
   ```powershell
   python scripts/seed_demo_data.py --plate 43A12345 --embedding-file path/to/nam_driver_embedding.json
   ```

---

## 2. Hướng Dẫn Chạy Web User, Admin Dashboard & Backend FastAPI

### Cách 1 (Khuyên dùng — Chỉ 1 lệnh duy nhất, KHÔNG cần cài Node.js)
FastAPI Backend tại cổng `8000` đã tích hợp sẵn cả API lẫn giao diện React Web User (`/user`), trang Đăng nhập (`/login`) và Admin Dashboard (`/admin`):

```powershell
cd c:\PBL4\doan_PBL4
edge-server\.venv\Scripts\uvicorn.exe smart_parking.interfaces.http.app:app --host 127.0.0.1 --port 8000
```

- Mở trình duyệt **Microsoft Edge** tại **`http://127.0.0.1:8000/login`** → Đăng nhập **`viet_user` (`Viet@123`)** để vào giao diện **Web User (`/user`)**: xem sơ đồ mặt bằng 2D 4 ô đỗ, đặt giữ ô 60 phút, xem đồng hồ đếm ngược đồng bộ server, bấm **"Xem đường đi (Góc nhìn người lái)"** và xem lịch sử cá nhân.
- Mở song song trình duyệt **Google Chrome** tại **`http://127.0.0.1:8000/login`** → Đăng nhập **`admin` (`Admin@123`)** để vào giao diện **Admin Dashboard (`/admin`)**: giám sát chi tiết 4 ô, phiên xe, đặt chỗ, độ mới cảm biến IR và duyệt thủ công (`Manual Review`).
- Tài liệu API tương tác (Swagger UI): **`http://127.0.0.1:8000/docs`**.

### Cách 2 (Tách riêng Backend cổng `8000` và Frontend cổng `5173`)
Nếu muốn chạy tách riêng 2 cổng (phục vụ dev frontend hoặc khi máy đã cài Node.js LTS):
- **Terminal 1 (Backend FastAPI cổng `8000`):**
  ```powershell
  cd c:\PBL4\doan_PBL4
  edge-server\.venv\Scripts\uvicorn.exe smart_parking.interfaces.http.app:app --host 127.0.0.1 --port 8000
  ```
- **Terminal 2 (Frontend cổng `5173`):**
  - *Không cần Node.js:* `edge-server\.venv\Scripts\python.exe dashboard\serve_frontend.py`
  - *Hoặc dùng Node.js + Vite:* `cd dashboard && Copy-Item .env.example .env && npm install && npm run dev`
- Sau đó mở trình duyệt tại **`http://localhost:5173/login`** (chi tiết kịch bản test xem thêm tại [dashboard/README.md](dashboard/README.md)).

---

## 3. Quy Trình Ghép & Test Khi Lắp Phần Cứng Thật (2 ESP32-S3 + 6 Cảm Biến IR + Camera)

*(Chi tiết kịch bản demo đầy đủ từng bước xem tại [docs/setup/demo-runbook.md](docs/setup/demo-runbook.md)).*

1. **Bật ngưỡng kiểm tra cảm biến thật trong `edge-server/.env`:**
   - Đặt `SLOT_STALE_SECONDS=30` (phát hiện mất tín hiệu cảm biến sau 30 giây), `DEMO_VEHICLE_PLATE` khớp biển số dán trên xe mô hình thật (ví dụ `43A12345`), và cấu hình MQTT/khóa thiết bị theo tài liệu bàn giao Duy.
2. **Nạp dữ liệu mẫu khuôn mặt thật (KHÔNG dùng `--init-slots-free`):**
   ```powershell
   edge-server\.venv\Scripts\python.exe edge-server\scripts\seed_demo_data.py --plate 43A12345 --embedding-file path\to\nam_driver_embedding.json
   ```
   Lúc đầu 4 ô sẽ ở trạng thái `Unknown` (`Chưa đủ dữ liệu / Lỗi cảm biến`) cho tới khi mạch ESP32 gửi gói IR thật đầu tiên.
3. **Kiểm tra cảm biến IR thật (`T02`):**
   - Cấp nguồn hai S3, chạy broker cục bộ và FastAPI theo `scripts/start_backend.ps1`.
   - Mở Admin (`http://127.0.0.1:8000/admin`) tab **📡 Cảm Biến IR & Thiết Bị**: 4 ô tự chuyển xanh **`Có thể đặt / Nhận xe`**. Che tay lên `IR_A1` → web tự nhảy **`Đang có xe`** qua WebSocket; rút nguồn ESP32 > 30 giây → web tự cảnh báo **`Chưa đủ dữ liệu / Lỗi cảm biến`**.
4. **Test vòng đời trọn vẹn xe đặt trước (`T07` & `T15`):**
   - **Web User (`viet_user`)** đặt giữ ô `B1` (60 phút) → xem mô phỏng góc nhìn người lái.
   - Đưa xe mô hình `43A-123.45` + tài xế tới **Cổng Vào (`Gate IN`)** → AI nhận diện khớp → barie mở → xe qua cổng (`2. Đối soát cổng vào` → `3. Đã qua cổng vào`).
   - Đặt xe vào ô **`B1`** che cảm biến `IR_B1` → Web User tự cập nhật **`✓ XE ĐÃ ĐỖ ỔN ĐỊNH TRONG Ô B1`** + đồng hồ tính giờ gửi xe, ô `B1` đổi xanh dương **`Đang có xe`**.
   - Đưa xe rời ô `B1` tới **Cổng Ra (`Gate OUT`)** → ô `B1` vẫn được giữ an toàn cho tới khi qua hẳn cổng (`T15`) → đối chiếu khuôn mặt phiên lúc vào khớp → barie ra mở → xe rời bãi → phiên `Closed`, booking `Completed`, ô `B1` tự mở xanh trở lại!
5. *(Tùy chọn khi chưa cắm phần cứng muốn tự test 4 bước trên laptop)*: Dùng script giả lập CLI `edge-server\scripts\simulate_gate_flow.py --step checkin|enter|park|exit`.

---

## 4. Hướng Dẫn Backup & Restore MySQL Trước Buổi Demo (`mysqldump`)

### 3.1. Sao lưu (Backup) toàn bộ Database ra file `.sql` trước buổi Demo
Sau khi đã seed tài khoản, biển số xe mô hình và mẫu khuôn mặt tài xế chuẩn:
```powershell
& "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe" `
  -h 127.0.0.1 -P 3306 -u root -p `
  --single-transaction --routines --triggers --hex-blob `
  --default-character-set=utf8mb4 `
  smart_parking_pbl4 > c:\PBL4\doan_PBL4\backup_smart_parking_demo.sql
```
*(Lưu ý: Cờ `--hex-blob` bắt buộc có để bảo toàn nguyên vẹn cột nhị phân `embedding_blob` đã mã hóa AES-256-GCM trong `user_face_templates` và `session_face_templates`).*

### 3.2. Khôi phục (Restore) Database về trạng thái sạch ngay trong buổi Demo
```powershell
& "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" `
  -h 127.0.0.1 -P 3306 -u root -p `
  --default-character-set=utf8mb4 `
  smart_parking_pbl4 < c:\PBL4\doan_PBL4\backup_smart_parking_demo.sql
```

---

## 5. Chạy Bộ Kiểm Thử Nghiệm Thu Tự Động (`T01`–`T20` & `VII.4`)

```powershell
cd c:\PBL4\doan_PBL4
edge-server\.venv\Scripts\pytest.exe edge-server\tests\test_system_acceptance.py -v
```

---

## 6. Tài Liệu Thiết Kế & Bàn Giao Chi Tiết
- [Sơ đồ ERD MySQL 9 bảng](docs/diagrams/database-erd.mmd)
- [Từ điển dữ liệu & Quy tắc khóa giao dịch MySQL](docs/database/mysql-schema.md)
- [Chính sách mã hóa AES-256-GCM & Lưu trữ mẫu khuôn mặt](docs/database/data-retention.md)
- [Hợp đồng API, Xác thực & Tích hợp dữ liệu cho Duy & Nam](docs/protocols/api-and-integration-contract.md)
- [Kịch bản chạy Demo & Test lắp phần cứng thật (Demo Runbook)](docs/setup/demo-runbook.md)
- [Hướng dẫn chạy & test Web User / Admin Dashboard](dashboard/README.md)
- [Danh mục kịch bản kiểm thử nghiệm thu](docs/testing/acceptance-scenarios.md)
