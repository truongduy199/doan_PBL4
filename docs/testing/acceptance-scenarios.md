# Kịch Bản Kiểm Thử Nghiệm Thu (Acceptance Scenarios — Phần Việc Của Việt)

Bộ kiểm thử tự động trong `edge-server/tests/test_viet_acceptance_suite.py` kiểm chứng toàn bộ các ca nghiệm thu bắt buộc:

| Mã Ca | Tên Kịch Bản Nghiệm Thu | Kỳ Vọng Kết Quả |
| :--- | :--- | :--- |
| **T01** | Ô `Free` vật lý nhưng đã `Reserved` | Không cấp cho khách vãng lai (`ERR_PARKING_FULL`), không cho người khác đặt trùng (`409 SLOT_ALREADY_RESERVED`). |
| **T02** | Ô `Unknown`, `Fault` hoặc dữ liệu IR quá hạn (`> 30s`) | Không tính là khả dụng (`is_available = False`), giao diện hiển thị `"Chưa đủ dữ liệu / Lỗi cảm biến"`, từ chối đặt chỗ. |
| **T03** | 2 giao dịch đặt cùng 1 ô `A1` đồng thời | Chỉ đúng 1 giao dịch thành công (`201 Created`), giao dịch còn lại nhận `409 Conflict` kèm trạng thái ô mới. |
| **T04** | Tải lại trang (F5) khi booking còn 20 phút | `GET /api/bookings/current` trả đúng `expires_at` ban đầu và `remaining_seconds = 1200`, không bao giờ reset về 60 phút. |
| **T05** | Hết hạn booking quá 60 phút chưa check-in | Worker `expire_overdue_bookings` chuyển booking sang `'Expired'`, tháo `parking_slots.active_booking_id = NULL`, giữ `bookings.slot_id`. |
| **T06** | Bảo vệ booking đang `Checkin_pending` sát hạn | Khi xe đã bắt đầu đối soát tại cổng vào sát mốc 60 phút, worker hết hạn tuyệt đối không hủy hoặc lấy mất ô của xe. |
| **T07** | Luồng xe đặt trước qua cổng vào (`Gate IN`) | Đối chiếu `user_face_templates`, tạo mẫu riêng trong `session_face_templates`, khi qua cổng tháo `active_booking_id` và giữ `reserved_session_id`. |
| **T08** | Cập nhật mẫu tài khoản khi xe đang đỗ trong bãi | Mẫu cũ chuyển sang `'Replaced'`, mẫu mới là `'Active'`; lượt xe ra cổng OUT vẫn đối chiếu với `session_face_templates` lúc vào. |
| **T13** | Chống lặp sự kiện cổng (`event_id` idempotency) | Gửi lặp cùng `event_id` vào `confirm_gate_in_passage` / `confirm_gate_out_passage` không tạo trùng bản ghi và không ghi đè `entry_time` / `exit_time`. |
| **T15** | Giữ quyền ô khi xe đang lùi ra cổng (`Exit_pending`) | Dù cảm biến IR tại ô báo `Free` khi xe rời ô tiến ra cổng OUT, `reserved_session_id` vẫn giữ ô cho đến khi xe qua hẳn cổng OUT. |
| **T19** | Tác vụ xóa mẫu khuôn mặt phiên hết hạn (`Retention`) | Chỉ xóa `session_face_templates` của phiên đã `Closed`/`Cancelled` và quá `expires_at`; giữ nguyên `user_face_templates` và phiên đang hoạt động. |
| **T20** | Trung thực trạng thái `liveness_status` | Mẫu nạp nội bộ không chạy live scan ghi `liveness_status = 'Not_used'`, `liveness_score = NULL`; lượt quét thực tế hợp lệ ghi `'Passed'`. |
| **VII.4** | Phân quyền RBAC & Bảo mật dữ liệu theo Role | Token `USER` gọi `/api/admin/*` bị chặn `403 Forbidden`; `USER` không xem được biển số/booking của người khác trên `/api/slots` và không hủy được booking của người khác. |
