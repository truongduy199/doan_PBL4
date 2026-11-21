# Firmware ESP32-S3 N16R8 OV5640 — Bãi Đỗ Xe Thông Minh PBL4

> Cấu hình và trình tự tích hợp hiện hành: [Bàn giao phần Duy](../../docs/setup/duy-handover.md). Firmware thật dùng HTTP/MQTT; Serial i/o chỉ bật trong môi trường Wokwi. Các đoạn hướng dẫn DevKit/Serial/ba camera phía dưới là mô tả cũ, không dùng để đấu nối hoặc triển khai bản hai S3.

Firmware chuẩn theo kiến trúc phần cứng đã chốt tại **Mục IV & Mục VIII Báo cáo PBL4**:
- **Chỉ sử dụng 2 bo ESP32-S3 N16R8 gắn camera OV5640** (đã loại bỏ hoàn toàn bo ESP32 DevKit V1, 2 LED xanh/đỏ ngoài và 2 điện trở 220 ohm):
  1. **Bo S3 Biển số kiêm Điều khiển (`BOARD_ROLE = BOARD_ROLE_PLATE_CTRL`)**:
     - Thu ảnh biển số IN/OUT qua camera OV5640 và gửi JPEG lên laptop qua `HTTP POST /api/device/images`.
     - Đọc và lọc nhiễu không chặn (non-blocking) **6 cảm biến IR**: 2 IR cổng (`IN`, `OUT`) và 4 IR ô đỗ (`A1`, `A2`, `B1`, `B2`).
     - Điều khiển **2 Servo Barie**, màn hình **OLED SSD1306 128x64 I2C** (`0x3C`) và **Còi MH-FMD**.
     - Giao tiếp sự kiện, snapshot, lệnh mở cổng và ACK qua **MQTT over Wi-Fi**.
  2. **Bo S3 Khuôn mặt độc lập (`BOARD_ROLE = BOARD_ROLE_FACE_CAM`)**:
     - Nhận yêu cầu chụp từ topic `parking/cameras/face/capture` và gửi JPEG khuôn mặt đúng lượt (`event_id`, `gate_id`, `roi`) qua `HTTP POST /api/device/images`.

---

## 1. Bảng Chân Phần Cứng (S3 Biển Số Kiêm Điều Khiển — Mục IV.2)

| Tín hiệu | GPIO trên ESP32-S3 | Ghi chú kỹ thuật |
| :--- | :--- | :--- |
| **IR Cổng IN & OUT** | `GPIO1` (IN), `GPIO2` (OUT) | Mức `LOW` = có xe/vật cản; lọc nhiễu `IR_FILTER_MS = 50 ms`. |
| **4 IR Ô đỗ (`A1`..`B2`)** | `A1: GPIO14`, `A2: GPIO21`, `B1: GPIO41`, `B2: GPIO42` | Khởi động ở trạng thái `Unknown` cho tới khi đủ cửa sổ ổn định. |
| **2 Servo Barie** | `GPIO38` (IN), `GPIO39` (OUT) | PWM 50 Hz, **LEDC Timer 1, Kênh 2 & 3, 14-bit** (tách khỏi Timer 0 của Camera). |
| **Còi MH-FMD** | `GPIO20` | Active `LOW` (`LOW` = bật, `HIGH` = tắt). Không dùng USB native trên `GPIO20`. |
| **OLED SSD1306 128x64** | `SDA: GPIO40`, `SCL: GPIO47` | Giao tiếp I2C, địa chỉ `0x3C`. |
| **Camera OV5640 & PSRAM** | `GPIO4..13`, `15..18`, PSRAM `GPIO35..37` | Giữ nguyên PSRAM cho frame buffer JPEG; không gắn microSD, để trống USB-OTG. |

---

## 2. Hợp Đồng Giao Tiếp HTTP & MQTT (Mục VIII.2)

- **Gửi sự kiện cổng (`S3 -> Backend`)**: `parking/gates/IN/detected`, `parking/gates/OUT/detected` (`event_id`, `gate_id`, `device_id`, `boot_id`, `sequence`, trạng thái IR ổn định và xác nhận `PASSAGE_CONFIRMED` sau 3 giây trống liên tục).
- **Gửi snapshot 4 ô đỗ (`S3 -> Backend`)**: `parking/slots/snapshot` (`device_id`, `boot_id`, `sequence`, `slots: {A1..B2}`, `sensors: [...]`).
- **Nhận yêu cầu chụp ảnh (`Backend -> 2 S3`)**: `parking/cameras/plate/capture`, `parking/cameras/face/capture` → S3 chụp frame mới và gửi `HTTP POST /api/device/images` kèm headers `X-Event-Id`, `X-Camera-Id`, `X-Gate-Id`, `X-ROI`, `X-Frame-Id`.
- **Nhận lệnh mở cổng (`Backend -> S3 điều khiển`)**: `parking/gates/IN/command`, `parking/gates/OUT/command` (kiểm tra khớp `event_id`, chống lặp `command_id`, kiểm tra hạn lệnh và xe còn hiện diện trước khi nâng servo).
- **Phản hồi ACK & Heartbeat (`S3 -> Backend`)**: `parking/devices/{device_id}/ack` (tách riêng `ack_received`, `servo_command_issued` với sự kiện xe qua cổng) và `parking/devices/{device_id}/status`.

---

## 3. Chế Độ Mô Phỏng Trên Wokwi (Mục VIII.3)

Mạch mô phỏng Wokwi: `https://wokwi.com/projects/481261560534933505`
- Đặt `#define ENABLE_OV5640_CAMERA 0` trong `config.example.h` khi chạy trên Wokwi.
- Khi IR cổng phát hiện xe (`Waiting_backend`), gõ phím **`i`** (cho cổng IN) hoặc **`o`** (cho cổng OUT) trong Serial Monitor để giả lập quyết định cấp phép từ Backend. Khi IR cổng trống liên tục đủ **3 giây**, barie tự động đóng và hoàn tất lượt.
