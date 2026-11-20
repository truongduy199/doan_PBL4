# Hệ Thống Bãi Đỗ Xe Thông Minh IoT (PBL4 — Smart Parking System)

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

## 2. Hướng Dẫn Chạy Backend FastAPI & Frontend Web User / Admin

### Bước 2.1: Khởi chạy Backend FastAPI (`edge-server`)
```powershell
cd c:\PBL4\doan_PBL4\edge-server
pip install -e ".[dev]"
uvicorn smart_parking.interfaces.http.app:app --host 127.0.0.1 --port 8000 --reload
```

### Bước 2.2: Khởi chạy Frontend React + Vite (`dashboard`)
```powershell
cd c:\PBL4\doan_PBL4\dashboard
Copy-Item .env.example .env
npm install
npm run dev
```
- Mở trình duyệt **Microsoft Edge** tại `http://localhost:5173/login` -> Đăng nhập **`viet_user` (`Viet@123`)** để vào giao diện **Web User (`/user`)**: xem sơ đồ 4 ô đỗ, đặt giữ ô 60 phút, xem đồng hồ đếm ngược đồng bộ server, bấm **"Xem đường đi (Góc nhìn người lái)"** và xem lịch sử cá nhân.
- Mở song song trình duyệt **Google Chrome** tại `http://localhost:5173/login` -> Đăng nhập **`admin` (`Admin@123`)** để vào giao diện **Admin Dashboard (`/admin`)**: giám sát chi tiết 4 ô, phiên xe, đặt chỗ, thiết bị cảm biến IR và duyệt thủ công (`Manual Review`).

---

## 3. Hướng Dẫn Backup & Restore MySQL Trước Buổi Demo (`mysqldump`)

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

## 4. Chạy Bộ Kiểm Thử Nghiệm Thu Tự Động (`T01`–`T20` & `VII.4`)

```powershell
cd c:\PBL4\doan_PBL4
python edge-server/tests/test_viet_acceptance_suite.py
```

---

## 5. Tài Liệu Thiết Kế & Bàn Giao Chi Tiết
- [Sơ đồ ERD MySQL 9 bảng](docs/diagrams/database-erd.mmd)
- [Từ điển dữ liệu & Quy tắc khóa giao dịch MySQL](docs/database/mysql-schema.md)
- [Chính sách mã hóa AES-256-GCM & Lưu trữ mẫu khuôn mặt](docs/database/data-retention.md)
- [Danh mục kịch bản kiểm thử nghiệm thu](docs/testing/acceptance-scenarios.md)
