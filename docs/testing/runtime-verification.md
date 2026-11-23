# Kết quả kiểm tra tích hợp phần mềm

## Kết nối lại khi cấp nguồn ngoài - 23/11/2026

- Sau reset, backend/Mosquitto vẫn chạy và tài khoản MQTT hai bo xác thực thành công. Laptop vẫn ở hotspot 2,4 GHz và IP cũ. Log USB tạm thời của bo điều khiển cho thấy Wi-Fi đã kết nối, camera sẵn sàng nhưng MQTT trả `-2` (chưa mở được TCP tới broker); chưa xác định nguyên nhân sâu hơn của lần lỗi TCP ban đầu.
- Kết nối sau đó tự phục hồi. Không nạp firmware hoặc thay đổi firewall/cấu hình mạng trong đợt chẩn đoán này. Không kết luận lỗi nguồn chỉ từ việc thiếu cổng COM khi dùng nguồn ngoài.
- Người dùng đã rút USB chẩn đoán và cấp nguồn ngoài cho cả hai bo. Windows không còn cổng COM, nhưng heartbeat mới của cả hai bo tiếp tục tăng, camera sẵn sàng và cả bốn IR có dữ liệu mới. Luồng xem kiểm tra nhận được JPEG từ cả `cam_plate` và `cam_face` qua Wi-Fi. USB laptop không phải điều kiện vận hành.

## Reset dữ liệu lượt xe giữ tài khoản - 23/11/2026

- Thêm CLI Python xem trước mặc định và wrapper PowerShell dừng/khởi động backend khi áp dụng. Người dùng xác nhận đã ngắt nguồn cả hai ESP trước khi reset thật.
- Reset trên MySQL thật đã xóa một phiên, một mẫu mặt phiên, hai đặt chỗ, 47 sự kiện cổng và nhật ký thử. Bốn ô trở về `Unknown`, xóa liên kết phiên/booking và dữ liệu boot/sequence cũ để chờ IR thật.
- Đối chiếu trước/sau xác nhận dữ liệu tài khoản (gồm password hash), BLOB mẫu mặt tài khoản, danh tính xe, mã ô/cảm biến và các cấu hình khác không thay đổi. Biển số xe USER thử nghiệm và riêng `DEMO_VEHICLE_PLATE` được đổi theo yêu cầu; ADMIN/USER vẫn đăng nhập được.
- Bổ sung kiểm tra định dạng sê-ri chữ+số để chuỗi biển số đăng ký mới không bị chặn. Chuẩn hóa giữ chữ/số viết hoa và bỏ dấu chấm, gạch ngang, khoảng trắng.
- **78 tests passed** với DB kiểm thử trong RAM. Có kiểm tra preview không đổi dữ liệu, xóa đúng phạm vi, giữ nguyên tài khoản/template, rollback sau lỗi giữa chừng, không đoán xe khi có nhiều xe và từ chối biển số trùng xe khác. PowerShell parse đạt. Sau reset thật, backend báo AI READY, không còn lượt/phiên cũ.
- Hướng dẫn: [Reset dữ liệu test](../setup/reset-test-data.md).

## AI nhận diện và lưu mẫu phiên thật - 23/11/2026

- Sửa ảnh phản chiếu ngang ở cảm biến; ảnh AI dùng UXGA 1600×1200, xem MJPEG giữ VGA. YOLO/OCR được nạp sẵn khi backend khởi động và dùng kích thước phát hiện 1280 để giữ chi tiết biển số nhỏ. Hai firmware build/nạp và dashboard build đạt.
- Camera thật đã OCR đúng biển số mô hình; nhận diện khuôn mặt/liveness đạt. Người dùng thử IR IN, xác nhận barie mở và xe vào A1. MySQL có phiên `Active`/`Parked_confirmed`, kèm mẫu `buffalo_l` 512-D float32, liveness `Passed`, ciphertext 2064 byte và metadata `AES-256-GCM`. Đọc/giải mã mẫu trong RAM trả vector chuẩn L2 bằng 1; không in hoặc lưu vector/ảnh ra file.
- Thử OUT thực tế còn có các lượt OCR thiếu/nhầm ký tự, thiếu/nhiều mặt, lỗi khung liveness hoặc điểm đối chiếu chưa đạt. Các mẫu mới của đúng người theo xác nhận người dùng có điểm 0,5604..0,5975; ảnh dashboard cho thấy một lượt đạt 0,614, vẫn dưới ngưỡng 0,65. Phiên chưa được đóng trong đợt kiểm tra này; không thay mẫu vào hoặc hạ ngưỡng để ép mở.
- Bổ sung ba ảnh mỗi camera cho lượt xe, deadline 8 giây. OCR cần ít nhất hai ảnh thống nhất; mặt cần ít nhất hai mẫu hợp lệ và nhất quán trước khi tổng hợp. Giữ chế độ một ảnh để tương thích; ảnh trùng/ID ngoài danh sách không tăng số mẫu.
- Dashboard tách kết quả đọc biển số, trích xuất đặc trưng, liveness, lưu mẫu và điểm đối chiếu. Nhãn cũ “Khuôn mặt hợp lệ” được đổi thành “Đã trích xuất đặc trưng khuôn mặt”; đối chiếu được ghi rõ đã đạt/chưa được duyệt để tránh nhầm với xác thực thành công.
- Bộ kiểm thử hiện tại **71 passed**, DB kiểm thử trong RAM; bao gồm burst, bỏ phiếu OCR, ngăn gộp các mẫu mặt thiếu nhất quán, model readiness và không lộ embedding qua API. Trạng thái `READY` yêu cầu nạp được cả model biển số và khuôn mặt.

## Chuyển sang MJPEG - 23/11/2026

- Hai bo đã build/nạp và xác minh hash; heartbeat của COM5/COM6 báo `stream_transport=mjpeg`. Cả backend và dashboard đã cập nhật. Ảnh AI vẫn chụp và gửi riêng qua `/api/device/images`; kiểm tra chụp tĩnh sau stream nhận được ảnh mới từ cả hai camera.
- ESP gửi multipart JPEG trên một HTTP POST chunked giữ kết nối tới backend. Dashboard mở hai HTTP GET MJPEG có xác thực quản trị, không nhận JPEG Base64 qua polling. Metadata cập nhật mỗi giây; chỉ giữ khung mới nhất trong RAM, không lưu video/ảnh xuống đĩa.
- Đo tại endpoint xem MJPEG thật, hai camera đồng thời: biển số **59 khung/12,16 giây = 4,85 FPS**; khuôn mặt **57 khung/12,28 giây = 4,64 FPS**. Nội dung của tất cả các khung trong mẫu đều khác nhau, JPEG giải mã được. Đây là tốc độ tại đầu xem HTTP, chưa phải phép đo tốc độ vẽ màn hình trình duyệt.
- IR OUT đang hiện diện đã tự kích hoạt MJPEG. Sau khi người dùng bỏ vật che, lượt chuyển `CANCELLED`, hai cổng về `Idle`, hai bo báo `streaming=false` và backend kết thúc luồng. Lượt đầu sau nạp trả `CAPTURE_TIMEOUT`; đợt kiểm tra này chưa đánh giá việc nhận diện AI thành công.
- Xem kiểm tra 30 giây: hai HTTP GET đều tự đóng sau **30,03 giây** với boundary kết thúc hợp lệ; heartbeat sau đó của cả hai bo báo ngừng phát. Không mở cổng thủ công khi đo.
- Bộ backend và mô-đun biển số: **64 passed**, dùng DB kiểm thử trong RAM. Có thêm kiểm tra multipart bị chia tại mọi vị trí byte, dữ liệu quá lớn/bị cắt, khóa sai, mã luồng cũ, quyền ADMIN/USER, ảnh JPEG và response MJPEG. Hai firmware và TypeScript/Vite build đạt.

## Kiểm tra stream trên hai bo thật - 23/11/2026

- Sau phản hồi ảnh đảo ngược, thêm `CAMERA_ROTATE_180=1` vào firmware, đảo đồng thời hai trục tại cảm biến. Hai môi trường build đạt; đã nạp và xác minh hash trên COM5/COM6. Sau khởi động lại, cả hai camera báo sẵn sàng và gửi được JPEG mới theo đúng mã chụp kiểm tra. Ảnh biển số đã đúng chiều; camera khuôn mặt lúc chụp đang hướng lên trần nên chưa xác nhận trực quan chiều khuôn mặt người. Ảnh kiểm tra chỉ xử lý trong RAM.
- Bo khuôn mặt COM5 và bo biển số/điều khiển COM6 đều online, camera sẵn sàng, hỗ trợ stream; bo điều khiển báo OLED sẵn sàng. Không nạp lại firmware trong lượt kiểm tra này.
- Kiểm tra xem trực tiếp qua API quản trị: trong 12 giây nhận 24 JPEG từ mỗi bo, khoảng 2 khung/giây mỗi camera. POST ảnh từ bo điều khiển trả HTTP 200.
- Kiểm tra phiên xem 30 giây: nhận ít nhất 51 khung biển số và 43 khung khuôn mặt; các mẫu lấy mỗi 2 giây có 15/12 nội dung JPEG khác nhau, xác nhận ảnh thay đổi. Backend tự kết thúc phiên; heartbeat sau đó của cả hai bo báo `streaming=false`. Tốc độ có dao động, không phải cam kết FPS liên tục.
- Người dùng đưa xe/vật tới IR IN thật: backend tự tạo luồng theo lượt xe (không phải preview). Bộ đếm ghi nhận ít nhất 74 khung biển số và 89 khung khuôn mặt. Khi người dùng đưa xe ra, lượt chuyển `CANCELLED`, luồng ngừng, hai bo báo `streaming=false`, cổng IN trở lại `Idle` và xóa event hiện hành.
- Lượt IR thử trả `INVALID_PLATE_FORMAT`; chưa chứng minh nhận diện biển số/khuôn mặt thành công hoặc xe qua barie. Không phát lệnh mở cổng thủ công trong kiểm tra này.
- Kiểm tra qua backend/API và log USB thật; công cụ truy cập Chrome lỗi nên chưa xác minh trực quan hai khung trên trình duyệt trong lượt này. Không lưu JPEG/khuôn mặt xuống đĩa; file chẩn đoán cục bộ chỉ ghi mã lượt, số khung và trạng thái dừng.
- Trước lượt kiểm tra phần cứng, bộ backend và mô-đun biển số đã đạt **59 passed** với DB kiểm thử trong RAM; firmware của hai môi trường và dashboard TypeScript/Vite đã build thành công. Các mục bên dưới là kết quả lịch sử tại thời điểm ghi, không phản ánh giới hạn môi trường hiện tại.

## Kiểm tra sau dọn source - 22/11/2026

- Đã loại 62 file nguồn dư thừa: Firebase runtime/rules/contracts và script thử cũ, AI đếm ô đỗ, workflow rỗng, sketch test chưa triển khai, kịch bản không có runner, khung đánh giá, ba fake rỗng, các file frontend dư và ba class khung biển số.
- Giữ test nghiệp vụ, `fake_mysql_db.py`, `dashboard/spa.py`, model và các cấu hình cục bộ. Sáu file mang tên người đã được đổi sang tên chức năng; lệnh và liên kết liên quan đã cập nhật.
- Toàn bộ `edge-server/tests` và `modules/license_plate_yolo_numpy/tests`: **49 passed**. Bộ acceptance được ép dùng database trong RAM bằng `SystemAcceptanceTests._use_real_mysql = False`; không khởi tạo hoặc xóa database MySQL demo.
- `npm run build` trong `dashboard/`: TypeScript và Vite build đạt. Đây là kiểm tra build, chưa phải kiểm thử thao tác giao diện trên trình duyệt.
- `scripts/check_environment.py --runtime --network`: 0 vấn đề; MySQL và MQTT chấp nhận kết nối TCP. JSON contracts hợp lệ, không còn import `smart_parking` trỏ đến module đã xóa; các liên kết tài liệu vừa sửa hợp lệ.
- Đã sửa một test tích hợp cũ để gửi đủ `vehicle_id` theo API đặt chỗ. Kiểm tra frontend trong bộ acceptance hỗ trợ cả bản Vite và giao diện dự phòng.
- Bộ test vẫn phát cảnh báo về phiên bản Starlette/httpx và khóa JWT dành riêng cho test. Không có test thất bại. Chưa chạy kiểm thử Vitest frontend trong đợt này.

Các kết quả này không chứng minh độ chính xác AI, liveness hoặc phần cứng thật. Đợt dọn dẹp không nạp bo, thay đổi `.env`/`config.local.h` hoặc dừng backend/broker.

## Lịch sử kiểm tra - 21/11/2026

| Phạm vi | Kết quả | Giới hạn |
| --- | --- | --- |
| `test_gate_runtime.py` | 17/17 đạt | Repository thật, DB kiểm thử cô lập, AI được tiêm kết quả; kiểm tra ảnh dùng decoder giả để kiểm tra giao thức. |
| `test_system_acceptance.py` | 14 đạt, 1 bỏ qua | Dùng DB kiểm thử tương thích MySQL trên SQLite trong môi trường này. Bài phục vụ frontend bỏ qua vì thiếu FastAPI/uvicorn. |
| Phân tích cú pháp Python | 166 file, không lỗi cú pháp | Không thay cho import và chạy các thư viện native. |
| `scripts/check_environment.py` | Không phát hiện lỗi nguồn/JSON | Chế độ không có `--runtime` chỉ kiểm tra mã nguồn và JSON. |
| `scripts/check_contracts.py` | 10 file JSON đọc được | Chỉ kiểm tra cú pháp JSON, không chứng minh payload thiết bị tuân thủ mọi schema. |
| Script khởi động PowerShell | Cú pháp hợp lệ | Chưa khởi động dịch vụ thật. |
| PlatformIO | Có ba môi trường cấu hình | Chưa biên dịch toolchain ESP32. |

17 bài kiểm thử tích hợp luồng cổng bao gồm luồng walk-in vào/đỗ/ra, tạo phiên trước khi duyệt booking, không mở lặp, tách ACK với passage, timeout chụp, hủy lượt khi xe rời trong lúc AI, lỗi database, mất broker, xác thực HTTP thiết bị, metadata/ROI/frame, ảnh trùng/quá hạn, snapshot boot cũ, khôi phục xác nhận passage sau backend restart và thiếu model không tự tải/giả lập thành công.

Bài nghiệm thu manual review cũ được cập nhật: APPROVE một event lưu trong DB nhưng không còn lượt thiết bị phải trả 409; DENY vẫn ghi audit và không mở cổng. Không giữ kỳ vọng cũ cho phép mở cổng chỉ từ một bản ghi review cũ.

## Chưa chạy được trong môi trường thực hiện

- Bộ pytest/OpenCV và HTTP FastAPI thật: thiếu thư viện cần thiết; thử tải bằng pip không thành công do không phân giải được địa chỉ máy chủ gói.
- Build/type-check Vite/React: chưa có `dashboard/node_modules` và npm trong PATH môi trường. Đã tách `src/test` khỏi build sản phẩm để phần kiểm thử Vitest không chặn build giao diện.
- Biên dịch firmware bằng PlatformIO/Arduino, kết nối Mosquitto/MySQL thật, mDNS thật và suy luận model thật.
- Nạp hai S3, kiểm tra camera/PSRAM/IR/servo/OLED/còi/nguồn, thời gian vòng điều khiển, độ trễ và demo có xe thật.

Không dùng các kết quả trên để công bố độ chính xác AI, FPS, độ trễ GPIO hay hiệu năng InnoDB. Chưa thực hiện thao tác xóa dữ liệu demo, cài broker thành service, đổi mạng/firewall hoặc nạp firmware lên thiết bị.

## Tệp cần dùng khi ghép hệ thống

- [Cấu hình và trình tự triển khai](../setup/system-integration.md)
- [Hợp đồng HTTP/MQTT](../protocols/mqtt-http-device-contract.md)
- [Bảng chân và nguồn](../setup/hardware-wiring.md)
- [Môi trường build firmware](../../firmware/platformio.ini)
- [Kiểm tra trước khi chạy](../../scripts/check_environment.py)
- [Khởi động backend](../../scripts/start_backend.ps1)
### 23/11/2026 — Tự nhận diện lại khi xe còn chờ

- Sửa backend: timeout chụp và lỗi OCR/chất lượng ảnh có thể phục hồi chuyển sang chờ thử lại ít nhất 2 giây, cần heartbeat controller mới, cùng boot/event/cổng đang chờ. Nhận ảnh tuần tự từng camera thay vì dồn 3 lệnh vào hàng đợi ESP có sức chứa 2. Ảnh vòng cũ không được dùng lại. Chưa nhận diện đạt thì chưa ghi phiên/chiếm ô.
- Bổ sung kiểm tra timeout có nhường cổng còn lại, OCR lỗi rồi đọc đạt và cấp ô/mở một lần, xe rời IR, heartbeat hết hạn, ảnh vòng cũ, thời hạn qua cổng sau khi xe phải chờ quét lâu. Giữ kiểm tra người thật và ngưỡng đối chiếu.
- Bộ kiểm tra toàn hệ thống: 82 passed trên DB giả cô lập; đặt DEMO_VEHICLE_PLATE=43A12345 riêng tiến trình kiểm tra để khớp fixture cũ. Sau bổ sung thời hạn duyệt: nhóm runtime/camera 40 passed. Dashboard TypeScript/Vite build đạt. Không thay biển số thật 85H650346 hoặc dữ liệu DB thật.
- Đã khởi động lại backend; health và /admin HTTP 200, AI READY, MQTT connected, cả hai bo online bằng nguồn ngoài. Không sửa hoặc nạp firmware trong lượt này.
- Lượt thật đã thấy vòng 1 CAPTURE_TIMEOUT tự chuyển vòng 2, hai camera tiếp tục gửi hình. Ảnh biển số đến muộn bị HTTP 409; tăng CAPTURE_TIMEOUT_SECONDS riêng môi trường thực từ 8 lên 30 giây, lệnh chụp riêng vẫn tối đa 14 giây để tương thích firmware giới hạn 15 giây. Chưa xác nhận nhận diện/cấp ô thành công sau tăng thời gian: chờ người dùng bỏ vật khỏi IR rồi kích hoạt lượt mới. Lượt CAPTURE_TIMEOUT cũ vẫn ở Review_required trên bo, không tự dựng lại hoặc tự duyệt sau khi backend khởi động lại.
- Xác nhận thực tế sau tăng thời gian lúc 09:33 ngày 23/11: IR IN kích hoạt, nhận đủ bộ ảnh, AI duyệt sau khoảng 6 giây. OCR `92V576492` / `92V5-764.92`, người dùng xác nhận đúng biển in đang thử. Khuôn mặt tổng hợp từ 2 mẫu hợp lệ, kiểm tra người thật Passed; tạo phiên `72c01ac2-4a1f-4748-825f-74c92a64a190`, cấp B2. Lệnh OPEN duy nhất được controller ACK_ACCEPTED / SERVO_OPEN_ISSUED. Sau khi qua cổng, lượt COMPLETED, controller Idle; phiên Active / Parked_confirmed tại B2. Đây là lượt vãng lai; biển tài khoản thử nghiệm 85H650346 được giữ nguyên.
- Demo đặt trước A1 ngày 23/11/2026: biển `85H650346`, booking `6d62eeb0-41e6-4cd2-b5f9-1f826e9bb5b6`. Entry event `ev-bfdbc25e0-IN-001fb0ad-00000007`: BOOKING_ENTRY_APPROVED, cấp A1, OPEN ACK_ACCEPTED, lưu mặt thực tế 2 mẫu Passed vào phiên `92825047-42cf-46ce-8fb3-c43821e4f832`; lúc 09:46:21 xe qua cổng, A1 nhận xe và phiên Active/Parked_confirmed, booking Checked_in. Exit event `ev-bfdbc25e0-OUT-0020e698-00000008`: đọc đúng biển, 3 mẫu mặt Passed, similarity 0.7881, EXIT_FACE_MATCH_APPROVED; OPEN ACK_ACCEPTED. Lúc 09:47:23 xe qua cổng ra: lượt COMPLETED, phiên Closed có exit_time, booking Completed, cảm biến A1 Free. Theo dõi qua API, không can thiệp mở cổng hay sửa dữ liệu lượt xe.
- Demo xe vãng lai B2 ra ngày 23/11/2026: phiên `72c01ac2-4a1f-4748-825f-74c92a64a190`, biển `92V576492`. Lần đầu FACE_QUALITY_FAILED do mặt quay ngang, barie giữ đóng, phiên vẫn Active; sau khi người dùng để IR OUT trống đã xác nhận controller Idle và lượt cũ CANCELLED. Lượt mới `ev-bfdbc25e0-OUT-00258cba-0000000a` đọc đạt, mặt 3 mẫu Passed, similarity 0.8847, EXIT_FACE_MATCH_APPROVED, OPEN ACK_ACCEPTED/SERVO_OPEN_ISSUED. Xe ra lúc 09:52:19, lượt COMPLETED, phiên Closed có exit_time, B2 Free. Chỉ theo dõi; không mở thủ công hay thay mẫu mặt/ngưỡng.
- Cảnh báo tư thế từ MJPEG ngày 23/11/2026: triển khai worker detector/quality riêng, tối đa 2 Hz, thích nghi theo thời gian xử lý, dùng ảnh mới nhất và ưu tiên inference cổng. Dashboard hiển thị hướng dẫn riêng, không coi POSE_READY là duyệt danh tính. Bộ kiểm tra đầy đủ 87 passed; sau bổ sung kiểm tra giảm tần suất, nhóm hướng dẫn 4 passed; TypeScript/Vite build đạt. Kiểm tra cover detector-only không lấy identity, nhiều mặt/không mặt/tư thế, ảnh mới nhất/throttle, ưu tiên gate, kết quả quá hạn/stream đổi/dừng, không tạo phiên hoặc lệnh cổng.
- Thử stream thật 10:03–10:04: API trả WAITING_FRAME, NO_FACE, mặt sát mép; lượt tiếp theo người dùng quay mặt rồi nhìn thẳng, nhận FACE_QUALITY_FAILED (quay ngang) → POSE_READY. Thời gian mẫu detector/quality khoảng 43–132 ms, median lượt đầu 67.9 ms; hai bo tiếp tục gửi ảnh. Chỉ thử preview, không tạo lượt xe hoặc phát OPEN, không thay dữ liệu đã demo. Backend và dashboard đã cập nhật; không nạp lại firmware. Đây là đo khi preview, chưa phải đo tải đồng thời với một lượt xe thật mới.
