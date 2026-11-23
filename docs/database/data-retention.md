# Chính Sách Mã Hóa & Lưu Trữ Dữ Liệu Khuôn Mặt (Data Retention & Encryption Policy)

Ảnh xem trên dashboard chỉ dành cho ADMIN: mỗi camera giữ tối đa một JPEG gần nhất trong RAM, khung mới thay khung cũ, hết hạn sau 30 giây và được dọn bởi tác vụ bảo trì. Không lưu lịch sử video. API ảnh trả `Cache-Control: no-store, private`; giao diện bỏ ảnh khi hết hạn hoặc rời màn hình camera/tổng quan/thiết bị. Không ghi ảnh khuôn mặt xuống đĩa hoặc database. Chụp/xem trực tiếp kiểm tra qua dashboard không chạy AI, không tạo phiên và không phát lệnh barie; yêu cầu xe tại cổng luôn được ưu tiên. Phiên xem kiểm tra tự dừng sau 30 giây; luồng theo lượt xe chỉ được gia hạn khi heartbeat mới xác nhận đúng lượt xe còn hiện diện.

---

## 1. Mã Hóa Vector Khuôn Mặt 512-D (`EmbeddingCipher`)

1. **Thuật toán & Quản lý khóa:**
   - Toàn bộ vector đặc trưng khuôn mặt 512 chiều (`float32`, chuẩn hóa L2) trong `user_face_templates` và `session_face_templates` được mã hóa bằng **AES-256-GCM** trước khi ghi xuống MySQL.
   - Khóa bí mật đọc từ biến môi trường `EMBEDDING_SECRET_KEY` (tuyệt đối không lưu trong cơ sở dữ liệu hay hard-code trong source code).
   - Cột `encryption_metadata` (`JSON`) chỉ lưu `nonce`, `tag`, `alg: "AES-256-GCM"`; phiên bản khóa lưu ở cột `key_version`.
2. **Kiểm tra toàn vẹn trước khi mã hóa:**
   - Vector phải là mảng 1 chiều có đúng `512` phần tử kiểu `float32`.
   - Toàn bộ phần tử phải hữu hạn (`np.all(np.isfinite(vector_np))`).
   - Chuẩn L2 phải đạt $\approx 1.0 \pm 10^{-3}$.
3. **Tính trung thực của trạng thái Liveness (`T20`):**
   - Với mẫu nạp nội bộ qua công cụ seed/import không chạy kiểm tra chống giả mạo trực tiếp trên camera, hệ thống bắt buộc lưu `liveness_status = 'Not_used'` và `liveness_score = NULL` (tuyệt đối không giả mạo thành `'Passed'`).

---

## 2. Tách Bạch Mẫu Tài Khoản (`user_face_templates`) và Mẫu Phiên (`session_face_templates`)

1. **Khi xe đặt trước vào cổng (`Gate IN` - `T07`):**
   - Hệ thống đối sánh khuôn mặt tài xế với mẫu `Active` trong `user_face_templates`.
   - Khi đạt, hệ thống vẫn tạo một bản ghi riêng biệt trong `session_face_templates` gắn với `session_id` của lượt gửi xe đó.
2. **Khi xe ra cổng (`Gate OUT` - `T08`):**
   - Hệ thống bắt buộc lấy mẫu khuôn mặt từ `session_face_templates` của chính `session_id` đang hoạt động để đối sánh 1:1.
   - Ngay cả khi `user_face_templates` của chủ tài khoản được cập nhật hoặc thay thế (`Replaced`) trong lúc xe đang đỗ trong bãi, lượt xe ra cổng vẫn đối chiếu chính xác với mẫu phiên lúc vào.

---

## 3. Chính Sách Hủy Mẫu Phiên Sau Khi Kết Thúc (`RetentionService` - `T19`)

1. **Thiết lập hạn xóa khi đóng phiên:**
   - Khi xe hoàn tất qua cổng ra (`sessions.status = 'Closed'`), hệ thống gán `session_face_templates.expires_at = exit_time + INTERVAL SESSION_TEMPLATE_RETENTION_HOURS HOUR` (mặc định 24 giờ).
2. **Quy tắc xóa an toàn (`purge_expired_session_templates`):**
   - Chỉ xóa các bản ghi `session_face_templates` có phiên liên kết ở trạng thái `'Closed'` hoặc `'Cancelled'` **và** `expires_at <= now_utc`.
   - **Không bao giờ** xóa mẫu của phiên đang hoạt động (`'Entry_pending'`, `'Active'`, `'Exit_pending'`).
   - **Không bao giờ** xóa mẫu tài khoản định danh trong `user_face_templates`.
   - Mọi lượt xóa đều ghi nhật ký kiểm toán `RETENTION_PURGE` vào bảng `parking_logs`.
