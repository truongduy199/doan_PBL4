# Hợp Đồng API, Xác Thực & Tích Hợp Dữ Liệu (Bàn Giao Cho Duy & Nam)

Tài liệu này chốt giao diện xác thực, REST/WebSocket API và các hàm dịch vụ dữ liệu Python trong tầng dữ liệu của **Việt** để **Duy** (cổng vào/ra, ESP32 IR, Admin Dashboard) và **Nam** (AI Biển số/OCR & InsightFace Buffalo-L) tích hợp trực tiếp, sạch và an toàn giao dịch.

---

## 1. Hợp Đồng Xác Thực & Phân Quyền (Thống Nhất Với Duy)

- **Cơ chế kép (Dual Transport):**
  - `POST /api/auth/login` trả về `access_token` (JWT HS256) trong JSON body **và** set HTTP-only cookie `access_token`.
  - Frontend lưu token theo `sessionStorage` và gửi kèm header `Authorization: Bearer <token>` + `credentials: "include"`, cho phép chạy song song 2 phiên **ADMIN** (Chrome) và **USER** (Edge) trên cùng 1 laptop.
- **Thu hồi phiên khi đăng xuất:**
  - `POST /api/auth/logout` xóa cookie **và** đưa Bearer token hiện tại vào danh sách thu hồi server-side (`TOKEN_REVOKED`, HTTP `401`).
- **Phân quyền (RBAC):**
  - `role = 'user'`: Chỉ truy cập `/api/me`, `/api/slots` (ẩn danh tính/biển số trên ô của người khác), `/api/bookings/*` (chỉ booking của chính mình), `/api/me/history`. Gọi vào `/api/admin/*` trả `403 Forbidden (ADMIN_ROLE_REQUIRED)`.
  - `role = 'admin'`: Truy cập đầy đủ `/api/slots` (thấy đầy đủ người đặt, biển số, mã phiên, `last_seen_at`), `/api/admin/sessions`, `/api/admin/bookings`, `/api/admin/reviews`, `POST /api/admin/reviews/{event_id}/decision`, `/api/admin/devices`, `/api/admin/logs`.
- **Không mở public signup, không cho thêm/sửa xe hoặc tải ảnh khuôn mặt trên web.**

---

## 2. Danh Sách REST & Realtime Endpoints (FastAPI)

| Method | Endpoint | Quyền | Chức năng |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/login` | Public | Đăng nhập bằng `username`, `password` (xác thực hash & `status='Active'`). |
| `POST` | `/api/auth/logout` | Authenticated | Thu hồi token hiện tại & xóa cookie. |
| `GET` | `/api/me` | Authenticated | Hồ sơ tài khoản, danh sách xe định danh & trạng thái mẫu khuôn mặt (không trả BLOB). |
| `GET` | `/api/slots` | Authenticated | Trạng thái tổng hợp 4 ô (`A1`, `A2`, `B1`, `B2`) kèm `server_time`, che giấu dữ liệu theo role. |
| `POST` | `/api/bookings` | USER | Đặt giữ ô 60 phút (hỗ trợ header `X-Idempotency-Key`, chống đặt trùng 409 Conflict). |
| `GET` | `/api/bookings/current` | USER | Booking hiện hành kèm `server_time` & `remaining_seconds` để reload không reset đồng hồ. |
| `GET` | `/api/bookings/{booking_id}` | Owner / ADMIN | Chi tiết booking. |
| `POST` | `/api/bookings/{booking_id}/cancel` | Owner / ADMIN | Hủy booking khi còn `Reserved`, chưa hết hạn và chưa check-in tại cổng. |
| `GET` | `/api/me/history` | Authenticated | Lịch sử đặt chỗ và lịch sử gửi xe của chính tài khoản trong token. |
| `GET` | `/api/admin/sessions` | ADMIN | Toàn bộ phiên xe kèm `booking_expires_at` & đếm ngược. |
| `GET` | `/api/admin/bookings` | ADMIN | Toàn bộ đặt chỗ hiện hành và lịch sử. |
| `GET` | `/api/admin/reviews` | ADMIN | Sự kiện cổng (`Review_required`) & bất thường đỗ xe (`Parking_review_required`, `Parking_timeout`). |
| `POST` | `/api/admin/reviews/{event_id}/decision` | ADMIN | Ghi nhận quyết định `APPROVE` / `DENY` kèm `reason` và ghi log `MANUAL_REVIEW`. |
| `GET` | `/api/admin/devices` | ADMIN | Độ mới dữ liệu 4 cảm biến IR (`last_seen_at`, `last_boot_id`, `last_sequence`). |
| `GET` | `/api/admin/logs` | ADMIN | Nhật ký kiểm toán `parking_logs` gần nhất (đã lọc bỏ dữ liệu nhạy cảm). |
| `WS` / `GET` | `/api/ws` & `/api/events/stream` | Realtime | Phát sự kiện ngay sau khi transaction MySQL commit. |

---

## 3. Các Hàm Dịch Vụ Dữ Liệu Nội Bộ Cho Duy (`GateDataService` & `RetentionService`)

Module: `smart_parking.application.services.gate_data_service.GateDataService`
*(Tầng dữ liệu tuyệt đối **không** tự chạy suy luận AI và **không** tự phát lệnh điều khiển servo/MQTT).*

1. **Xe đặt trước vào cổng (`Gate IN`):**
   - `begin_booking_checkin(plate_number, event_id, device_id="GATE_IN", now_utc=None)` -> Khóa `vehicles -> parking_slots -> bookings`, chuyển booking sang `Checkin_pending`, trả vector 512-D đã giải mã từ `user_face_templates` để Nam đối sánh 1:1 ngoài transaction.
   - `confirm_booking_entry_permission(booking_id, event_id, session_face_template_data, command_id=None, ocr_confidence=None, now_utc=None)` -> Tạo `sessions (Entry_pending)`, lưu mẫu phiên riêng vào `session_face_templates`, gán `parking_slots.reserved_session_id`, cập nhật `gate_events (Approved)`.
2. **Khách vãng lai vào cổng (`Gate IN`):**
   - `allocate_walkin_entry(plate_number, event_id, session_face_template_data, command_id=None, device_id="GATE_IN", ocr_confidence=None, now_utc=None)` -> Chọn ô thỏa mãn `available(slot)` (không bao giờ lấy ô đang `Reserved`), tạo phiên `Entry_pending` và `session_face_templates`.
3. **Xác nhận qua cổng / Lỗi / Hủy phiên chưa qua cổng:**
   - `confirm_gate_in_passage(event_id, now_utc=None)` (idempotent theo `event_id`) -> Chuyển session sang `Active` (`entry_time`, `Parking_pending`), booking sang `Checked_in`, tháo `active_booking_id = NULL`, giữ `reserved_session_id`.
   - `deny_gate_event(event_id, gate_id, device_id, reason_code, booking_id=None, session_id=None, ...)` -> Ghi `Denied`, hoàn trả booking `Checkin_pending` về `Reserved` (hoặc `Expired` nếu quá hạn).
   - `cancel_unpassed_entry_session(event_id, reason_code="ERR_GATE_TIMEOUT", now_utc=None)` -> Hủy phiên `Entry_pending` khi xe không đi qua barie, nhả `reserved_session_id`, giữ/hết hạn booking đúng quy tắc.
4. **Cập nhật cảm biến IR 4 ô:**
   - `update_ir_slot_snapshot(device_id, boot_id, sequence, slots_payload, received_at=None)` -> Lọc trùng/cũ `sequence` theo `boot_id`, cập nhật 4 ô và chuyển `Parking_pending -> Parked_confirmed | Parking_review_required | Parking_timeout`.
5. **Xe ra cổng (`Gate OUT`):**
   - `prepare_exit_verification(plate_number, event_id, device_id="GATE_OUT", now_utc=None)` -> Trả vector 512-D giải mã từ **`session_face_templates`** của chính phiên đang hoạt động (không lấy từ `user_face_templates`).
   - `approve_exit_permission(session_id, event_id, command_id=None, ...)` -> Chuyển `sessions.status = 'Exit_pending'` (vẫn giữ `reserved_session_id` dù IR báo trống).
   - `confirm_gate_out_passage(event_id, now_utc=None)` (idempotent theo `event_id`) -> Chuyển session `Closed` (`exit_time`), đặt `session_face_templates.expires_at`, tháo `reserved_session_id = NULL`, chuyển booking liên quan sang `Completed`.
6. **Duyệt thủ công & Retention:**
   - `flag_gate_review_required(...)` & `record_manual_review_decision(event_id, admin_user_id, action, reason, ...)`
   - `RetentionService.purge_expired_session_templates(now_utc=None)`

---

## 4. Định Dạng File Bàn Giao Embedding 512-D Từ Công Cụ Buffalo-L Của Nam

File JSON đầu ra để nạp bằng lệnh `python scripts/seed_demo_data.py --plate 43A12345 --embedding-file driver_embedding.json`:
```json
{
  "embedding": [0.0123, -0.0456, "... tổng cộng đúng 512 số float32 đã chuẩn hóa L2 ..."],
  "model_id": "buffalo_l",
  "model_version": "insightface-buffalo_l-v1.0",
  "config_version": "cfg-2026-11-18",
  "quality_score": 0.92,
  "liveness_status": "Not_used",
  "liveness_score": null
}
```
*(Nếu công cụ nạp ảnh nội bộ không chạy live anti-spoofing, bắt buộc giữ `liveness_status: "Not_used"` và `liveness_score: null`).*
