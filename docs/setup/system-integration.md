# Cấu hình và tích hợp hệ thống

Kiến trúc áp dụng: hai ESP32-S3 N16R8/OV5640, MySQL trên laptop, HTTP ảnh JPEG và MQTT sự kiện/lệnh. Bo `s3_plate_ctrl` đọc sáu IR, điều khiển hai servo/OLED và chụp biển số; bo `s3_face_cam` chụp khuôn mặt. Không có DevKit, camera toàn cảnh hay AI đếm ô đỗ trong luồng này.

## 1. Mã đã triển khai

- Firmware tách vòng điều khiển và tác vụ mạng bằng FreeRTOS/queue. Chỉ vòng điều khiển chạm cảm biến, servo và OLED; HTTP, camera, mDNS, reconnect và MQTT chạy trong tác vụ mạng.
- Hai cổng đợi quyền backend, kiểm tra event/command/hạn, kiểm tra xe còn hiện diện, chờ IR trống liên tục 3 giây và mở lại khi phát hiện vật trong lúc đóng. Chỉ phát một xác nhận passage cho mỗi lượt, kể cả có vật xuất hiện lại lúc đóng.
- Sự kiện cổng có ACK ứng dụng và retry trong RAM; không đồng nhất ACK nhận lệnh, ra lệnh servo và xe qua cổng. PubSubClient publish QoS 0; backend publish QoS 1. Không retain lệnh hoặc yêu cầu chụp.
- HTTP xác thực `X-Device-Key`, giới hạn dung lượng, kiểm tra đúng camera/device/event/frame/gate/ROI, ảnh quá hạn, ảnh trùng và lượt đang hoạt động. Frame suy luận được giải phóng sau xử lý/timeout. Dashboard ADMIN có ảnh JPEG gần nhất của mỗi camera trong RAM tối đa 30 giây; không ghi ảnh mặt xuống đĩa.
- Backend khởi động/dừng MQTT cùng FastAPI, xếp một lượt nhận diện, chặn xe IN tiếp theo khi còn phiên vào/chờ đỗ chưa rõ, gọi module AI và dữ liệu, gửi lệnh sau commit. Mất DB không tự cấp quyền.
- Model khuôn mặt được khởi tạo từ tài nguyên cục bộ; thiếu model/liveness không giả lập thành công. Đường tìm module biển số đã trỏ về đúng `modules/`.
- Admin có giám sát bo/camera/MQTT/hàng đợi/ACK, nhật ký và đếm ngược theo giờ server. Duyệt phải nhập lý do; sự kiện cũ không còn lượt thiết bị không được dùng để mở cổng. IN thiếu mẫu phiên hợp lệ phải chụp lại; không bỏ qua liveness.
- WebSocket/SSE chỉ gửi thông báo thay đổi, dữ liệu được tải lại qua REST có phân quyền.

## 2. Chuẩn bị môi trường

Chạy từ gốc repository, dùng Python phù hợp với bản InsightFace/addon liveness của dự án:

```powershell
py -3.11 -m venv edge-server/.venv
& ./edge-server/.venv/Scripts/python.exe -m pip install -e './edge-server[dev]'
& ./edge-server/.venv/Scripts/python.exe -m pip install -e ./modules/license_plate_yolo_numpy
Copy-Item edge-server/.env.example edge-server/.env
```

Không ghi đè `.env` đã cấu hình. Cài đúng bản InsightFace có addon liveness; việc có `liveness.onnx` không chứng minh thư viện đang thực thi addon. Không tự đổi ngưỡng để vượt kiểm tra liveness. Model/trọng số và dữ liệu tài xế thực tế cần được tích hợp từ tài nguyên AI/dữ liệu thật, không được thay bằng vector mẫu để tuyên bố demo thật.

Điền MySQL/khóa mã hóa theo hướng dẫn dự án. Với chế độ thiết bị, cấu hình thêm:

```dotenv
MQTT_ENABLED=true
MQTT_HOST=127.0.0.1
MQTT_USERNAME=pbl4_backend
MQTT_PASSWORD=<mat-khau-broker-da-tao>
DEVICE_API_KEY=<chuoi-ngau-nhien-dung-chung-voi-hai-bo>
MDNS_ENABLED=true
LAN_IP=<IPv4-LAN-cua-laptop>
```

`LAN_IP` là địa chỉ laptop trên hotspot 2.4 GHz. Không dùng localhost trên S3. ROIs để trống khi thử toàn khung; khi có vị trí dừng IN/OUT, cấu hình `PLATE_ROI_IN`, `PLATE_ROI_OUT`, `FACE_ROI_IN`, `FACE_ROI_OUT` theo pixel `x1,y1,x2,y2` của ảnh camera thật. Chỉ một tiến trình backend (`--workers 1`), vì hàng đợi nhận diện nằm trong bộ nhớ tiến trình.

## 3. Broker cục bộ

Cài Mosquitto và dùng cấu hình trong `deployment/mosquitto/`. Từ thư mục đó, tạo ba tài khoản; công cụ hỏi mật khẩu, không đưa mật khẩu vào lịch sử lệnh:

```powershell
mosquitto_passwd -c passwd pbl4_backend
mosquitto_passwd passwd s3_plate_ctrl
mosquitto_passwd passwd s3_face_cam
mosquitto -c mosquitto.conf -v
```

Chỉ dùng `-c` trong lệnh đầu để tạo file mới, vì nó ghi đè file mật khẩu. ACL giới hạn mỗi bo đúng topic của vai trò. File `passwd` được bỏ qua bởi Git. Repo cung cấp cấu hình, chưa cài service, sửa firewall hoặc khởi chạy broker trên máy người dùng. HTTP/MQTT cấu hình này dùng LAN riêng, chưa bật TLS; không đưa trực tiếp cổng 1883 ra Internet.

## 4. Firmware hai bo

Cài PlatformIO. Tạo `firmware/esp32_smart_parking/config.local.h` với các override riêng; file này được bỏ qua bởi Git:

```cpp
#pragma once
#undef WIFI_SSID
#define WIFI_SSID "TEN_HOTSPOT_2_4G"
#undef WIFI_PASSWORD
#define WIFI_PASSWORD "MAT_KHAU_WIFI"
#undef BACKEND_HOST
#define BACKEND_HOST "IP_LAN_LAPTOP"
#undef MQTT_USERNAME
#define MQTT_USERNAME DEVICE_ID
#undef MQTT_PASSWORD
#define MQTT_PASSWORD "MAT_KHAU_TAI_KHOAN_BO_NAY"
#undef DEVICE_API_KEY
#define DEVICE_API_KEY "GIONG_DEVICE_API_KEY_BACKEND"
```

Build/nạp từng bo riêng, chỉnh mật khẩu MQTT phù hợp trước khi nạp bo thứ hai:

```powershell
pio run -d firmware -e plate-controller
pio run -d firmware -e face-camera
# Chỉ chạy các lệnh upload sau khi chọn đúng bo/cổng thật:
pio run -d firmware -e plate-controller -t upload --upload-port COM5
pio run -d firmware -e face-camera -t upload --upload-port COM6
```

COM5/COM6 chỉ là ví dụ. Không đặt `BOARD_ROLE` trong `config.local.h`; vai trò do môi trường build xác định. Firmware thật tắt phím Serial i/o. Môi trường `wokwi-controller` bật mô phỏng và tắt camera; không dùng bản này để kết luận camera/Wi-Fi thật đã hoạt động.

Khi Wi-Fi lên lại, S3 tìm `pbl4-server.local`; nếu không tìm được dùng địa chỉ gần nhất trong NVS, sau đó địa chỉ cấu hình ban đầu. Địa chỉ gần nhất được lưu ở namespace `pbl4`, khóa `backend_host`. Firmware đồng bộ giờ từ `/api/device/time`, sau đó kiểm tra hạn tuyệt đối `expires_at_ms`; chưa đồng bộ giờ thì không thi hành lệnh. Snapshot/heartbeat định kỳ dùng để đối soát sau reconnect. Sau reset nguồn, backend giữ phiên/ô chưa xác nhận và cần quản trị đối soát; không tự phát lại OPEN.

### Kiểm tra hai camera thật trước khi chạy AI

Khi cả hai bo và broker đã online, có thể chạy từ gốc repository:

```powershell
& ./.venv/Scripts/python.exe scripts/check_camera_capture.py
```

Cổng HTTP cấu hình phải đang trống. Script mở server chẩn đoán tạm, chờ ESP đồng bộ giờ, yêu cầu mỗi camera chụp một JPEG và kiểm tra ảnh qua luồng nhận ảnh thiết bị hiện có. Mặc định không khởi tạo AI; không kết nối database, không gửi lệnh barie và không lưu ảnh xuống đĩa. Server tự dừng và giải phóng ảnh trong RAM sau phép thử. Kết quả đạt mặc định chỉ chứng minh chụp/truyền/giải mã JPEG và metadata, chưa chứng minh chất lượng nhận diện.

Thêm `--models-only` để kiểm tra nạp model cục bộ mà không chụp. Thêm `--ai` để chạy YOLO/OCR và pipeline khuôn mặt có yêu cầu liveness trên ảnh thật vừa nhận. Đặt biển số và một người trong đúng khung hình trước khi chạy. Chế độ AI này vẫn không ghi dữ liệu, không phát lệnh cổng và không đối sánh danh tính vì chưa cung cấp mẫu tham chiếu. Không in hoặc lưu vector khuôn mặt.

## 5. Chạy web và backend

Để demo không phụ thuộc Internet, build frontend trước khi ngắt Internet:

```powershell
Set-Location dashboard
npm install
npm run build
Set-Location ..
& ./edge-server/.venv/Scripts/python.exe scripts/check_environment.py --runtime --network
./scripts/start_backend.ps1
```

FastAPI ưu tiên `dashboard/dist/index.html` và `/assets` khi đã build; nếu chưa có dist thì dùng giao diện CDN hiện có, cần Internet để tải thư viện. Mở `/login`, đăng nhập ADMIN và USER bằng hai trình duyệt. `check_environment.py` chỉ kiểm tra, không seed/reset dữ liệu hoặc mở cổng. MySQL và dữ liệu demo dùng các script `init_database.py` và `seed_demo_data.py`, không tự xóa để chạy thử.

## 6. Kiểm thử và giới hạn kiểm chứng

```powershell
& ./edge-server/.venv/Scripts/python.exe -m unittest discover -s edge-server/tests -p test_gate_runtime.py -v
& ./edge-server/.venv/Scripts/python.exe -m unittest discover -s edge-server/tests -p test_system_acceptance.py -v
& ./edge-server/.venv/Scripts/python.exe -m pytest edge-server/tests/test_gate_workflow_and_ai_integration.py -v
& ./edge-server/.venv/Scripts/python.exe scripts/check_contracts.py
```

`test_gate_runtime.py` dùng repository thật với DB kiểm thử SQLite tương thích SQL và kết quả AI được tiêm vào. Đây là kiểm chứng nghiệp vụ, không chứng minh khóa InnoDB, độ chính xác AI hoặc phần cứng. Bộ acceptance hiện có dùng database riêng `smart_parking_pbl4_test` nếu MySQL test truy cập được; nó dọn bảng trong database test đó. Không đổi tên database test thành database demo.

Cần làm trên thiết bị thật: xác nhận đúng pinout bo mua thực tế, build toolchain, nạp hai bo, điện áp/nguồn servo, mức tín hiệu IR, hai camera đồng thời, FPS/latency, timeout mạng, mất nguồn/reconnect, bo điều khiển vẫn đọc IR khi HTTP chậm và demo đủ vòng booking/walk-in/ngoại lệ. Các phép đo chưa chạy không có số liệu công bố.

Chưa có thao tác quản trị tự hủy phiên `Entry_pending`/`PASSAGE_UNCERTAIN` trên web: phải đối soát vật lý trước khi dùng công cụ dữ liệu nội bộ để hủy phiên chưa qua. Đây là trạng thái cần xác minh, không tự nhả ô khi chưa rõ xe đã vào.
