# Giao thức thiết bị HTTP/MQTT hiện hành

## Định danh và bảo mật

Hai thiết bị: `s3_plate_ctrl`/`cam_plate`, `s3_face_cam`/`cam_face`. MQTT dùng ba tài khoản riêng và ACL tại `deployment/mosquitto/acl.conf`. HTTP dùng `X-Device-Key`; không cấu hình khóa thì endpoint thiết bị trả 401. Ảnh và embedding không nằm trong payload MQTT.

Mỗi bản tin thiết bị có `device_id`, `boot_id` không rỗng, `sequence` là số nguyên dương tăng trong một lần boot. Không retain bản tin sự kiện cổng. Subscriber bỏ bản tin retained và payload trên 16 KiB. Backend chống lặp snapshot và sự kiện; replay xác nhận qua cổng không được mở lại cổng.

## Topic

| Topic | Chiều và nội dung |
| --- | --- |
| `parking/gates/IN/detected`, `parking/gates/OUT/detected` | Controller → backend: envelope, `event_id` tối đa 36 ký tự, `gate_id`, `event_type`, `ir_stable_detected`; firmware bổ sung `occurred_at_ms` khi gửi. |
| `parking/devices/s3_plate_ctrl/event_ack` | Backend → controller: `boot_id`, `sequence`, `accepted`, lý do nếu có. Firmware ngừng retry bản tin tương ứng. Không phải xác nhận servo hay xe qua. |
| `parking/slots/snapshot` | Controller → backend: envelope và `slots: {A1, A2, B1, B2}` với `Free`, `Occupied`, `Unknown` hoặc `Fault`; `sensors` chứa slot/sensor ID, mức raw và trạng thái ổn định; server gắn thời điểm tiếp nhận. |
| `parking/cameras/plate/capture`, `parking/cameras/face/capture` | Backend → camera: `event_id`, `gate_id`, `roi`, `request_id`, `frame_id`, `issued_at`, `expires_at_ms`, `ttl_ms`. |
| `parking/gates/IN/command`, `parking/gates/OUT/command` | Backend → controller: `event_id`, `command_id`, `gate_id`, `action`, `assigned_slot_id`, `available_slots`, `issued_at`, `expires_at`, `expires_at_ms`, `expires_in_ms`. |
| `parking/devices/{device_id}/ack` | Thiết bị → backend: envelope, `event_id`, `command_id`, `gate_id`, `ack_received`, `accepted`, `servo_command_issued`, `reason`. |
| `parking/devices/{device_id}/status` | Thiết bị → backend: envelope, `online`, `camera_ready`, `queue_drops`; controller thêm state/event của hai cổng. |
| `parking/display/status` | Backend → controller: `available_slots` theo nghiệp vụ và `expires_at_ms`. OLED không dùng số ô IR trống để tự suy ra quyền nhận xe. |

`event_type`: `DETECTED`, `VEHICLE_LEFT_BEFORE_DECISION`, `BACKEND_DECISION_TIMEOUT`, `OBSTACLE_DURING_CLOSING`, `PASSAGE_CONFIRMED`. `action`: `OPEN`, `DENY`, `REVIEW_REQUIRED`. Firmware kiểm tra deadline tuyệt đối theo đồng hồ đã đồng bộ, đúng event/gate và xe vẫn hiện diện. OPEN/chụp không retain. Backend publish QoS 1; PubSubClient publish QoS 0 nên sự kiện cổng có retry/ACK ứng dụng. Outbox firmware nằm trong RAM, không bảo đảm tồn tại qua mất nguồn.

## HTTP

`GET /api/device/time`: cùng khóa thiết bị, trả `epoch_ms` và `server_time`; dùng đồng bộ thời gian nội bộ LAN, không phụ thuộc NTP Internet.

`POST /api/device/images`: `Content-Type: image/jpeg`, JPEG thô trong body, kèm `X-Device-Key`, `X-Device-Id`, `X-Camera-Id`, `X-Event-Id`, `X-Frame-Id`, `X-Gate-Id`, `X-ROI`. `frame_id` phải trùng yêu cầu chụp `req-plate-{event_id}` hoặc `req-face-{event_id}`. `ROI_IN`/`ROI_OUT` xác định làn; tọa độ crop được cấu hình trên backend, không tin tọa độ tự gửi từ thiết bị. Có dạng JSON/base64 cho thử nghiệm, cùng kiểm tra quyền và metadata.

Giới hạn JPEG 5 MiB, request tối đa 7 MiB; timeout chụp mặc định 5 giây tính từ lúc lượt được chọn, không tính lúc còn xếp hàng. Hai ảnh phải thuộc cùng một lượt hiện hành. Khi đủ ảnh, suy luận ở worker thread; DB transaction ngắn; command chỉ phát sau khi nghiệp vụ commit. Thiếu model/ảnh, sai metadata, nhiều mặt/biển hoặc liveness không đạt thì review, không mở.

## Khôi phục và quan sát

ACK lệnh chỉ cập nhật `ACK_ACCEPTED`/`ACK_REJECTED`; hết hạn không thấy ACK là `ACK_TIMEOUT`, lỗi gửi là `PUBLISH_FAILED`. Chỉ `PASSAGE_CONFIRMED` hợp lệ mới đổi trạng thái phiên qua cổng. Sau backend restart có thể đối chiếu event đã Approved trong DB để nhận xác nhận passage, không phát thêm OPEN. Event chưa xác nhận giữ ô/phiên để đối soát.

`GET /api/admin/devices` bổ sung `gateway` và `mqtt`; không trả ảnh, embedding, khóa hoặc mật khẩu. Heartbeat trên 20 giây là offline. Snapshot ô đỗ dùng cấu hình `SLOT_STALE_SECONDS`. Dashboard đọc log qua `/api/admin/logs`, duyệt qua `/api/admin/reviews/{event_id}/decision`, bắt buộc ADMIN và lý do.
