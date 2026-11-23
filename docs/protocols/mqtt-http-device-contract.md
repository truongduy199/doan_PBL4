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
| `parking/cameras/plate/stream`, `parking/cameras/face/stream` | Backend → camera: `action=START/STOP`, `event_id`, `stream_id`, `gate_id`, `roi`, `expires_at_ms`. START cấp phiên tối đa 30 giây; gia hạn giữ nguyên mã luồng và số thứ tự khung. STOP chỉ áp dụng khi khớp mã luồng/lượt. Không retain. |
| `parking/gates/IN/command`, `parking/gates/OUT/command` | Backend → controller: `event_id`, `command_id`, `gate_id`, `action`, `assigned_slot_id`, `available_slots`, `issued_at`, `expires_at`, `expires_at_ms`, `expires_in_ms`. |
| `parking/devices/{device_id}/ack` | Thiết bị → backend: envelope, `event_id`, `command_id`, `gate_id`, `ack_received`, `accepted`, `servo_command_issued`, `reason`. |
| `parking/devices/{device_id}/status` | Thiết bị → backend: envelope, `online`, `camera_ready`, `queue_drops`; controller thêm state/event của hai cổng. |
| `parking/display/status` | Backend → controller: `available_slots` theo nghiệp vụ và `expires_at_ms`. OLED không dùng số ô IR trống để tự suy ra quyền nhận xe. |

Firmware hiện gửi luồng qua `POST /api/device/mjpeg` với `Transfer-Encoding: chunked`, `Content-Type: multipart/x-mixed-replace; boundary=frame`. Headers kết nối: `X-Device-Key`, `X-Device-Id`, `X-Camera-Id`, `X-Event-Id`, `X-Stream-Id`, `X-Gate-Id`, `X-ROI`. Từng phần có `Content-Length`, `Content-Type: image/jpeg`, `X-Frame-Id` tăng dần theo mã luồng. Giới hạn mỗi phần 5 MiB, header 2 KiB và thời gian không có dữ liệu 5 giây; phiên vẫn chịu deadline/gia hạn MQTT. `/api/device/images` giữ nguyên cho ảnh AI; `/api/device/stream` được giữ tương thích với firmware cũ gửi từng JPEG.

Chụp AI theo burst dùng `CAPTURE_SAMPLE_COUNT` (1..5, triển khai hiện tại 3). Backend phát từng yêu cầu `capture`: ảnh đầu `req-{plate|face}-{event_id}`, ảnh tiếp theo thêm `-2`, `-3`. Thiết bị chỉ phản hồi đúng frame ID nhận được. Backend chỉ nhận các ID đã yêu cầu, bỏ ảnh trùng và đợi đủ số ảnh từ cả hai camera trước khi chạy AI; deadline chụp dùng `CAPTURE_TIMEOUT_SECONDS` (triển khai hiện tại 8 giây). Chụp kiểm tra qua dashboard vẫn lấy một ảnh mỗi camera, không chạy AI/đổi dữ liệu phiên.

`event_type`: `DETECTED`, `VEHICLE_LEFT_BEFORE_DECISION`, `BACKEND_DECISION_TIMEOUT`, `OBSTACLE_DURING_CLOSING`, `PASSAGE_CONFIRMED`. `action`: `OPEN`, `DENY`, `REVIEW_REQUIRED`. Firmware kiểm tra deadline tuyệt đối theo đồng hồ đã đồng bộ, đúng event/gate và xe vẫn hiện diện. OPEN/chụp không retain. Backend publish QoS 1; PubSubClient publish QoS 0 nên sự kiện cổng có retry/ACK ứng dụng. Outbox firmware nằm trong RAM, không bảo đảm tồn tại qua mất nguồn.

## HTTP

`GET /api/device/time`: cùng khóa thiết bị, trả `epoch_ms` và `server_time`; dùng đồng bộ thời gian nội bộ LAN, không phụ thuộc NTP Internet.

`POST /api/device/images`: `Content-Type: image/jpeg`, JPEG thô trong body, kèm `X-Device-Key`, `X-Device-Id`, `X-Camera-Id`, `X-Event-Id`, `X-Frame-Id`, `X-Gate-Id`, `X-ROI`. `frame_id` phải trùng yêu cầu chụp `req-plate-{event_id}` hoặc `req-face-{event_id}`. `ROI_IN`/`ROI_OUT` xác định làn; tọa độ crop được cấu hình trên backend, không tin tọa độ tự gửi từ thiết bị. Có dạng JSON/base64 cho thử nghiệm, cùng kiểm tra quyền và metadata.

Giới hạn JPEG 5 MiB, request tối đa 7 MiB; timeout chụp mặc định 5 giây tính từ lúc lượt được chọn, không tính lúc còn xếp hàng. Hai ảnh phải thuộc cùng một lượt hiện hành. Khi đủ ảnh, suy luận ở worker thread; DB transaction ngắn; command chỉ phát sau khi nghiệp vụ commit. Thiếu model/ảnh, sai metadata, nhiều mặt/biển hoặc liveness không đạt thì review, không mở.

## Khôi phục và quan sát

ACK lệnh chỉ cập nhật `ACK_ACCEPTED`/`ACK_REJECTED`; hết hạn không thấy ACK là `ACK_TIMEOUT`, lỗi gửi là `PUBLISH_FAILED`. Chỉ `PASSAGE_CONFIRMED` hợp lệ mới đổi trạng thái phiên qua cổng. Sau backend restart có thể đối chiếu event đã Approved trong DB để nhận xác nhận passage, không phát thêm OPEN. Event chưa xác nhận giữ ô/phiên để đối soát.

`GET /api/admin/devices` bổ sung `gateway` và `mqtt`; không trả ảnh, embedding, khóa hoặc mật khẩu. Heartbeat trên 20 giây là offline. Snapshot ô đỗ dùng cấu hình `SLOT_STALE_SECONDS`. Dashboard đọc log qua `/api/admin/logs`, duyệt qua `/api/admin/reviews/{event_id}/decision`, bắt buộc ADMIN và lý do.
### Tự quét lại khi xe còn chờ tại cổng

Backend nhận từng ảnh rồi mới yêu cầu mẫu tiếp theo của cùng camera, tối đa một lệnh chụp đang chờ trên mỗi bo. Mỗi vòng vẫn yêu cầu đủ số mẫu cấu hình; không dùng ảnh MJPEG cũ thay cho ảnh chụp nhận diện.

Nếu hết hạn nhận ảnh hoặc OCR/chất lượng khuôn mặt chưa đạt, backend chờ ít nhất 2 giây rồi thử bộ ảnh mới, khi heartbeat controller còn mới dưới 20 giây, cùng boot/event/cổng và trạng thái Waiting_backend hoặc Review_required. Mất thông tin hiện diện thì dừng tự thử và chuyển kiểm tra. Sự kiện xe rời IR hủy lượt ngay. Mỗi vòng nhường hàng đợi cho cổng còn lại.

Vòng đầu giữ `req-plate-{event_id}` / `req-face-{event_id}`; vòng sau thêm `-r2`, `-r3`… trước hậu tố mẫu `-2`, `-3`. Backend từ chối ảnh vòng cũ, ảnh ngoài thứ tự và ảnh trùng không chạy AI lần nữa. Bộ nhớ chỉ giữ một bộ ảnh của vòng hiện tại. Lỗi tạm thời trả `decision=Scanning`, chưa ghi phiên/chiếm ô/mở barie; lỗi mô hình, kiểm tra người thật, đối chiếu danh tính hoặc nghiệp vụ vẫn cần xử lý theo chính sách hiện có.

Khi AI đạt, giao dịch hiện có lưu phiên và mẫu mặt mã hóa, cấp ô hợp lệ rồi phát OPEN một lần. Thời hạn chờ xe qua cổng tính lại từ lúc duyệt, kể cả khi xe đã chờ quét lâu. Dashboard trả `scan_state` và `capture_round`, kể cả lúc camera chưa gửi ảnh đầu tiên.
### Hướng dẫn tư thế mặt trên stream

`GET /api/admin/cameras?images=0` trả thêm `guidance` cho cam_face khi stream đang hoạt động: `ok`, `reason_code`, `message`, thời điểm ảnh/kiểm tra và `processing_ms` nếu đã xử lý. Trạng thái chờ ảnh và ưu tiên nhận diện cổng không mang kết luận tư thế đạt. `POSE_READY` chỉ là hướng dẫn tư thế, không phải kết quả kiểm tra người thật hoặc duyệt mở cổng.

Worker riêng chỉ chạy detector SCRFD và kiểm tra chất lượng/landmark; không chạy ArcFace, liveness, OCR, không ghi database, không phát lệnh cổng. Chỉ dùng JPEG mới nhất trong RAM, không xếp hàng ảnh. Tối đa 2 lần/giây, tự giảm tần suất nếu xử lý chậm; nhường inference lock khi tác vụ quyết định cổng đang chạy/chờ. Kết quả ảnh cũ quá 3 giây hoặc thuộc stream đã dừng/đổi bị loại bỏ. Quyền admin và quy trình kiểm tra ảnh quyết định cổng giữ nguyên.
