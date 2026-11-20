# Hướng Dẫn Chạy & Kiểm Thử Web User + Admin Dashboard (Smart Parking PBL4)

Giao diện Web User Đặt Chỗ 60 Phút (kèm Mô phỏng góc nhìn người lái sau vô lăng 60fps cho 4 tuyến `A1`, `A2`, `B1`, `B2`) và Admin Dashboard xây dựng bằng **React + TypeScript + Tailwind CSS**, kết nối trực tiếp **FastAPI + MySQL/InnoDB** (đã loại bỏ hoàn toàn Firebase và dữ liệu mock giả).

---

## 1. Chuẩn Bị Trước Khi Chạy (Chỉ làm 1 lần hoặc khi reset DB)

1. **Bật MySQL trong XAMPP Control Panel** (cổng `3306`, user `root`, mật khẩu rỗng `""`).
2. **Đảm bảo file cấu hình `edge-server/.env` tồn tại** (nếu chưa có thì copy từ `edge-server/.env.example`):
   ```powershell
   cd c:\PBL4\doan_PBL4
   Copy-Item edge-server\.env.example edge-server\.env
   ```
3. **Khởi tạo 9 bảng MySQL & nạp dữ liệu mẫu (nếu database chưa có dữ liệu):**
   ```powershell
   edge-server\.venv\Scripts\python.exe edge-server\scripts\init_database.py
   edge-server\.venv\Scripts\python.exe edge-server\scripts\seed_demo_data.py --with-test-fixtures --init-slots-free
   ```

---

## 2. Cách Chạy Web User (Chọn 1 Trong 2 Cách)

### Cách 1 (Nhanh nhất — Chỉ 1 lệnh duy nhất, KHÔNG cần cài Node.js)
FastAPI Backend tại cổng `8000` đã tích hợp sẵn cả API lẫn giao diện Web User / Admin:

```powershell
cd c:\PBL4\doan_PBL4
edge-server\.venv\Scripts\uvicorn.exe smart_parking.interfaces.http.app:app --host 127.0.0.1 --port 8000
```

Sau khi terminal hiện `Uvicorn running on http://127.0.0.1:8000`, mở trình duyệt vào:
- 👉 **http://127.0.0.1:8000/login** (hoặc **http://localhost:8000/login**)

### Cách 2 (Tách riêng Backend port `8000` & Frontend port `5173`)
Mở **2 cửa sổ PowerShell** tại `c:\PBL4\doan_PBL4`:
- **Terminal 1 (Backend FastAPI port 8000):**
  ```powershell
  edge-server\.venv\Scripts\uvicorn.exe smart_parking.interfaces.http.app:app --host 127.0.0.1 --port 8000
  ```
- **Terminal 2 (Frontend port 5173 — không cần Node.js):**
  ```powershell
  edge-server\.venv\Scripts\python.exe dashboard\serve_frontend.py
  ```
  *(Hoặc nếu máy đã cài Node.js LTS: `cd dashboard && npm install && npm run dev`)*

Sau đó mở trình duyệt vào:
- 👉 **http://localhost:5173/login**

---

## 3. Tài Khoản Test & Checklist Trải Nghiệm Web User

| Vai trò | Username | Password | Xe định danh |
| :--- | :--- | :--- | :--- |
| **USER Demo** | `viet_user` | `Viet@123` | `43A-123.45` (`43A12345`) |
| **ADMIN** | `admin` | `Admin@123` | — |
| **USER Test 1** | `test_user_1` | `Test@123` | `43A-888.81` (`43A88881`) |
| **USER Test 2** | `test_user_2` | `Test@123` | `43A-888.82` (`43A88882`) |

### Kịch bản tự test nhanh trên trình duyệt:
1. **Đăng nhập USER (`viet_user` / `Viet@123`):** Kiểm tra thanh Header hiển thị đúng tên chủ xe, biển số `43A-123.45`, trạng thái mẫu khuôn mặt 512-D `Đã liên kết` (không có nút đăng ký/thêm xe/tải ảnh mặt).
2. **Xem sơ đồ mặt bằng 2D 4 ô (`A1`, `A2`, `B1`, `B2`):** Bấm chọn 1 ô xanh (`Có thể đặt / Nhận xe`), quan sát mũi tên dẫn hướng ở làn giữa tự đổi hướng theo ô đã chọn.
3. **Đặt giữ ô 60 phút:** Bấm **"🅿️ Đặt giữ ô (60 phút)"** → Modal **Mô phỏng góc nhìn sau vô lăng 60fps** tự động bật lên (barie mở, xi-nhan nhấp nháy, vô lăng đánh lái vào đúng ô đã đặt, radar 2D di chuyển đồng bộ). Thử tua thanh tiến trình, đổi tốc độ `1x/1.5x`, bấm **Xem lại** và **Thoát**.
4. **Kiểm tra reload đồng hồ (F5):** Đợi vài chục giây rồi bấm **F5 tải lại trang** → Đồng hồ đếm ngược tiếp tục đếm từ thời gian còn lại (`expires_at - server_time`), không reset về `60:00`.
5. **Kiểm tra bảo mật 2 trình duyệt song song:**
   - Mở tab/trình duyệt thứ 2 đăng nhập `test_user_1` (`Test@123`): thấy ô vừa đặt là **"Đã được đặt"**, **không lộ** biển số `43A-123.45` của `viet_user`.
   - Mở tab/trình duyệt khác đăng nhập `admin` (`Admin@123`): thấy đầy đủ biển số `43A-123.45`, tên người đặt `viet_user` và mã Booking.
6. **Hủy đặt chỗ & Lịch sử cá nhân:** Quay lại tab `viet_user`, bấm **"✕ Hủy đặt chỗ"** → xác nhận trong hộp thoại → ô đỗ xanh trở lại và xuất hiện dòng `Cancelled` trong tab **Lịch sử Đặt giữ ô**.
