# Demo Runbook & Quy Trình Test Khi Lắp Phần Cứng Thật (PBL4 Smart Parking IoT)

> Cấu hình và trình tự tích hợp hiện hành: [Hướng dẫn tích hợp hệ thống](../setup/system-integration.md). Firmware thật dùng HTTP/MQTT; Serial i/o chỉ bật trong môi trường Wokwi. Các đoạn hướng dẫn DevKit/Serial/ba camera phía dưới là mô tả cũ, không dùng để đấu nối hoặc triển khai bản hai S3.

Tài liệu này hướng dẫn quy trình chuẩn từ đầu đến cuối khi ghép **Phần cứng (ESP32 + 4 cảm biến IR + Barie + Camera)**, **AI nhận diện biển số/khuôn mặt**, **Điều phối cổng/MQTT** và **Database MySQL + FastAPI + Web User** để kiểm thử tích hợp và chạy demo bảo vệ đồ án.

---

## 1. Bước Chuẩn Bị Trước Khi Cắm Phần Cứng (Checklist)

1. **Chuyển cấu hình [edge-server/.env](../../edge-server/.env) sang chế độ phần cứng thật:**
   - Chỉnh ngưỡng quá hạn cảm biến IR về chuẩn vận hành thật (**30 giây**):
     ```env
     SLOT_STALE_SECONDS=30
     ```
     *(Lưu ý: khi test web thuần không cắm ESP32 ta để tạm `86400`, nhưng khi lắp mạch thật phải trả về `30` để hệ thống phát hiện đứt dây / mất kết nối ESP32 sau 30 giây).*
   - Kiểm tra `DEMO_VEHICLE_PLATE` khớp đúng biển số dán trên xe mô hình thật (ví dụ `43A12345`).
   - Kiểm tra `SERIAL_PORT` khớp cổng COM của ESP32 trong Device Manager (ví dụ `COM3`).
2. **Bật XAMPP MySQL** (cổng `3306`, user `root`, mật khẩu rỗng).
3. **Khởi tạo bảng và nạp mẫu khuôn mặt tài xế thật từ công cụ trích xuất Buffalo-L:**
   ```powershell
   cd c:\PBL4\doan_PBL4
   edge-server\.venv\Scripts\python.exe edge-server\scripts\init_database.py
   edge-server\.venv\Scripts\python.exe edge-server\scripts\seed_demo_data.py --plate 43A12345 --embedding-file path\to\nam_driver_embedding.json
   ```
   > **Lưu ý quan trọng:** Khi chạy với phần cứng thật, **KHÔNG** truyền cờ `--init-slots-free` để 4 ô khởi tạo ở trạng thái `'Unknown'` và chỉ chuyển xanh khi nhận đúng tín hiệu thật từ 4 cảm biến IR trên mạch ESP32.
4. **Sao lưu (Backup) snapshot DB sạch trước khi test / demo:**
   ```powershell
   & "C:\xampp\mysql\bin\mysqldump.exe" -h 127.0.0.1 -P 3306 -u root --single-transaction --routines --triggers --hex-blob --default-character-set=utf8mb4 smart_parking_pbl4 > backup_smart_parking_demo.sql
   ```

---

## 2. Khởi Chạy Hệ Thống & Kiểm Tra Kết Nối 4 Cảm Biến IR Thật

1. **Khởi động Backend + Web (cổng `8000`):**
   ```powershell
   cd c:\PBL4\doan_PBL4
   edge-server\.venv\Scripts\uvicorn.exe smart_parking.interfaces.http.app:app --host 127.0.0.1 --port 8000
   ```
2. **Cấp nguồn mạch ESP32 + 4 cảm biến IR (`IR_A1`..`IR_B2`) + Barie + Camera** và khởi chạy tiến trình cầu nối phần cứng/AI (gọi trực tiếp vào `GateDataService`).
3. **Mở song song 2 trình duyệt trên laptop:**
   - **Google Chrome** → `http://127.0.0.1:8000/login` → Đăng nhập **ADMIN** (`admin` / `Admin@123`).
   - **Microsoft Edge** → `http://127.0.0.1:8000/login` → Đăng nhập **USER Demo** (`viet_user` / `Viet@123`).
4. **Test 4 cảm biến IR (Kiểm chứng `T02` & Realtime WebSocket):**
   - Trên Chrome (Admin) → tab **📡 Cảm Biến IR & Thiết Bị**: ngay khi ESP32 gửi gói snapshot đầu tiên qua `update_ir_slot_snapshot(...)`, cả 4 cảm biến tự chuyển từ `Chưa đủ dữ liệu` sang **`Hợp lệ`**, `physical_status = Free`, `last_sequence` tăng dần.
   - **Đặt tay hoặc xe mô hình che `IR_A1`**: Cả màn hình Admin và Web User tự chuyển `A1` sang xanh dương **`Đang có xe`** ngay lập tức (không cần F5). Nhấc ra → tự về xanh lá **`Có thể đặt / Nhận xe`**.
   - **Rút nguồn / ngắt kết nối ESP32 thử 35 giây**: Quá `30s`, 4 ô tự chuyển sang cảnh báo **`Chưa đủ dữ liệu / Lỗi cảm biến`** và khóa nút đặt chỗ. Cắm lại nguồn → tự xanh lại.

---

## 3. Quy Trình Test Luồng Chính End-to-End: Xe Đặt Trước 60 Phút (`T07` & `T15`)

| Giai đoạn | Thao tác phần cứng & Web | Tầng dữ liệu và dịch vụ nghiệp vụ | Kết quả hiển thị tức thì trên Web User & Admin |
| :--- | :--- | :--- | :--- |
| **Bước 1: Đặt giữ chỗ trên Web User** | Trên Edge (`viet_user`), chọn ô xanh **`B1`** → bấm **"Đặt giữ ô B1 (60 phút)"**. Xem mô phỏng góc nhìn người lái sau vô lăng (không mở barie thật). | `POST /api/bookings` (`BookingService.create_booking`) | Web User hiện khung **`ĐẶT CHỖ ĐANG HIỆU LỰC`**, đồng hồ đếm ngược 60 phút, ô `B1` vàng **`Đã đặt trước`**. Bấm F5 đồng hồ vẫn đếm tiếp không reset (`T04`). |
| **Bước 2: Xe đến Cổng Vào (`Gate IN`)** | Đặt xe mô hình biển **`43A-123.45`** vào vị trí cảm biến Cổng Vào + tài xế thật nhìn vào Camera khuôn mặt. | `begin_booking_checkin` → AI đối sánh 1:1 với `user_face_templates` + Liveness | Web User sáng bước **`2. Đối soát cổng vào`** (`Checkin_pending`). Nút Hủy đặt chỗ tự khóa. |
| **Bước 3a: Mở Barie & Xe qua Cổng Vào** | AI xác nhận khớp mặt & biển số → ESP32 nâng barie Cổng Vào → cho xe chạy qua cảm biến xác nhận cổng vào → barie hạ đóng. | `confirm_booking_entry_permission` (tạo mẫu riêng vào `session_face_templates`) → `confirm_gate_in_passage` | Web User nhảy bước **`3. Đã vào bãi đỗ`** (`Checked_in`), hiện **`🚗 ĐÃ QUA CỔNG • ĐANG DI CHUYỂN VÀO Ô B1`**; ô `B1` hiện **`Đang cấp / Chờ xe đỗ`**. |
| **Bước 3b: Xe đỗ vào đúng ô `B1`** | Lái/đặt xe mô hình vào đúng khoang **`B1`** che cảm biến **`IR_B1`**. | ESP32 gửi snapshot `B1 = Occupied` → `update_ir_slot_snapshot` | Session tự chuyển **`Parked_confirmed`**. Web User đổi sang khung xanh **`✓ XE ĐÃ ĐỖ ỔN ĐỊNH TRONG Ô B1`** + đồng hồ đếm thời gian đang gửi xe; ô `B1` đổi xanh dương **`Đang có xe • 🚙 Đang đỗ: 43A-123.45`**. |
| **Bước 4a: Xe rời ô tiến ra Cổng Ra (`Gate OUT`)** | Nhấc/lái xe rời khỏi ô `B1` tiến tới Cổng Ra (`IR_B1` báo `Free` trước khi xe tới cổng). | `update_ir_slot_snapshot` (`B1 = Free`) | **Kiểm chứng `T15`**: Dù `IR_B1` đã báo trống, `B1` vẫn đang gắn `reserved_session_id` nên hiển thị **`Đang cấp / Chờ xe đỗ`**, user khác **không đặt được** cho tới khi xe ra hẳn bãi. |
| **Bước 4b: Đối chiếu khuôn mặt phiên & Rời bãi** | Xe dừng ở Cổng Ra, camera quét biển số `43A-123.45` và mặt tài xế → khớp → barie Cổng Ra mở → xe đi qua cổng → barie đóng. | `prepare_exit_verification` (đối sánh 1:1 với **`session_face_templates`**) → `approve_exit_permission` → `confirm_gate_out_passage` | Session chuyển **`Closed`**, booking chuyển **`Completed`**, ô `B1` tự nhả về xanh lá **`Có thể đặt / Nhận xe`**. Tab **Lịch sử Phiên gửi xe** trên Web User & Admin ghi đủ giờ vào, giờ ra, thời lượng. |

---

## 4. Các Kịch Bản Ngoại Lệ Cần Test Khi Ghép Phần Cứng

1. **Khách vãng lai không đặt trước (`T01`):**
   - `viet_user` đặt trước ô `B1` (ô `B1` vẫn trống vật lý).
   - Đưa xe lạ (ví dụ `92A-999.99`) vào Cổng Vào → backend gọi `allocate_walkin_entry(...)` → hệ thống chỉ cấp trong các ô trống còn lại (`A1`, `A2`, `B2`), tuyệt đối không lấy `B1`. Nếu cả 3 ô kia đều đầy thì từ chối (`ERR_PARKING_FULL`).
2. **Đỗ sai ô (`Parking_review_required`):**
   - Xe được cấp ô `B1` nhưng cố tình đặt vào ô `A2` (che `IR_A2`) → `update_ir_slot_snapshot` giữ nguyên `assigned_slot_id = B1` và đẩy cảnh báo `Parking_review_required` lên tab **🔍 Duyệt Thủ Công** trên Admin Dashboard.
3. **Khuôn mặt bất định / Duyệt thủ công (`Manual Review`):**
   - Khi tài xế che mặt hoặc góc nghiêng khiến độ tương đồng nằm giữa `T_reject` và `T_accept` → backend gọi `flag_gate_review_required(...)` → Admin vào tab **🔍 Duyệt Thủ Công**, nhập lý do và bấm **✓ Cho phép (`APPROVE`)** hoặc **✕ Từ chối (`DENY`)** → hệ thống gọi `POST /api/admin/reviews/{event_id}/decision` và ghi log kiểm toán `MANUAL_REVIEW`.
4. **Reset nhanh dữ liệu sạch sau mỗi lượt chạy thử:**
   ```powershell
   & "C:\xampp\mysql\bin\mysql.exe" -h 127.0.0.1 -P 3306 -u root --default-character-set=utf8mb4 smart_parking_pbl4 < backup_smart_parking_demo.sql
   ```
