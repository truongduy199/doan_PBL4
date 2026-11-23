#ifndef CONFIG_H
#define CONFIG_H

/**
 * Cấu hình Firmware ESP32-S3 N16R8 OV5640 (Mục IV.2, IV.3, IV.9 & VIII.2 Báo cáo PBL4)
 *
 * Chế độ biên dịch cho 2 bo ESP32-S3:
 * - BOARD_ROLE_PLATE_CTRL (1): Bo S3 biển số kiêm điều khiển 6 IR, 2 Servo, OLED, MQTT & HTTP Camera.
 * - BOARD_ROLE_FACE_CAM   (2): Bo S3 khuôn mặt độc lập (chỉ nhận yêu cầu chụp MQTT và gửi JPEG qua HTTP).
 */
#define BOARD_ROLE_PLATE_CTRL  1
#define BOARD_ROLE_FACE_CAM    2

#ifndef BOARD_ROLE
#define BOARD_ROLE             BOARD_ROLE_PLATE_CTRL
#endif

// Bật/tắt driver camera OV5640 (Tắt = 0 khi chạy mô phỏng trên Wokwi vì Wokwi chưa mô phỏng OV5640)
#ifndef ENABLE_OV5640_CAMERA
#define ENABLE_OV5640_CAMERA   1
#endif

// Cho phép nhận phím 'i' (mở IN) / 'o' (mở OUT) qua Serial Monitor để giả lập cấp phép trên Wokwi (Mục IV.2 & VIII.3)
#ifndef ENABLE_WOKWI_SERIAL_SIM
#define ENABLE_WOKWI_SERIAL_SIM 0
#endif

// Định danh thiết bị và Camera theo vai trò bo
#if (BOARD_ROLE == BOARD_ROLE_PLATE_CTRL)
#define DEVICE_ID              "s3_plate_ctrl"
#define CAMERA_ID              "cam_plate"
#define TOPIC_CAM_CAPTURE      "parking/cameras/plate/capture"
#define TOPIC_CAM_STREAM       "parking/cameras/plate/stream"
#else
#define DEVICE_ID              "s3_face_cam"
#define CAMERA_ID              "cam_face"
#define TOPIC_CAM_CAPTURE      "parking/cameras/face/capture"
#define TOPIC_CAM_STREAM       "parking/cameras/face/stream"
#endif

// Cấu hình mạng Wi-Fi Hotspot 2.4 GHz & Laptop Backend/Broker (Mục VIII.1)
#define WIFI_SSID              "PBL4_Hotspot_2.4G"
#define WIFI_PASSWORD          "12345678"
#define BACKEND_HOST           "192.168.137.1"
#define BACKEND_MDNS_HOSTNAME  "pbl4-server"
#define BACKEND_HTTP_PORT      8000
#define BACKEND_IMAGE_PATH     "/api/device/images"

#define MQTT_BROKER_HOST       BACKEND_HOST
#define MQTT_BROKER_PORT       1883
#define MQTT_USERNAME          ""
#define MQTT_PASSWORD          ""
#define DEVICE_API_KEY         ""

// Danh sách MQTT Topics chuẩn theo Mục VIII.2
#define TOPIC_GATE_IN_DETECTED   "parking/gates/IN/detected"
#define TOPIC_GATE_OUT_DETECTED  "parking/gates/OUT/detected"
#define TOPIC_SLOTS_SNAPSHOT     "parking/slots/snapshot"
#define TOPIC_GATE_IN_COMMAND    "parking/gates/IN/command"
#define TOPIC_GATE_OUT_COMMAND   "parking/gates/OUT/command"
#define TOPIC_DEVICE_ACK_FMT     "parking/devices/%s/ack"
#define TOPIC_DEVICE_STATUS_FMT  "parking/devices/%s/status"

// Cấu hình thời gian lọc nhiễu IR và đóng barie theo Mục IV.9 & Giám sát 4 ô đỗ Mục III.2
#define SERIAL_BAUD                 115200
#define GATE_IR_FILTER_MS           50UL     // IR_FILTER_MS = 50 ms cho 2 cảm biến cổng
#define SLOT_IR_STABLE_MS           250UL    // Cửa sổ ổn định riêng cho 4 cảm biến ô đỗ (hàng trăm ms)
#define GATE_CLEAR_DELAY_MS         3000UL   // Chờ trống liên tục 3 giây mới đóng barie
#define GATE_WAIT_BACKEND_TIMEOUT_MS 15000UL // Timeout chờ backend phản hồi khi xe đứng ở cổng
#define SNAPSHOT_INTERVAL_MS        3000UL   // Chu kỳ gửi snapshot định kỳ 4 ô đỗ + heartbeat
#define HEARTBEAT_INTERVAL_MS       5000UL   // Chu kỳ gửi trạng thái thiết bị

// Mức logic cảm biến IR theo Mục IV.2
#define IR_ACTIVE_STATE             LOW      // LOW = có vật cản/xe; HIGH = trống

// Cấu hình PWM Servo LEDC (Timer 1, Kênh 2 & 3, 14-bit, 50Hz - tách riêng khỏi Timer 0 của Camera)
#define SERVO_LEDC_TIMER            1
#define SERVO_IN_LEDC_CHANNEL       2
#define SERVO_OUT_LEDC_CHANNEL      3
#define SERVO_PWM_FREQ_HZ           50
#define SERVO_PWM_RES_BITS          14
#define SERVO_ANGLE_CLOSED          0
#define SERVO_ANGLE_OPEN            170      // Góc mở kế thừa chương trình test (Mục IV.9)
#define SERVO_MIN_PULSE_US          1000
#define SERVO_MAX_PULSE_US          2000

#define CAMERA_STREAM_INTERVAL_MS      200UL
#define CAMERA_STREAM_MAX_DURATION_MS  30000UL

// Correct the mounted OV5640 image relative to the driver's initial orientation.
// Flip vertically only: flipping both axes left plate text horizontally mirrored.
#define CAMERA_FLIP_VERTICAL           1
#define CAMERA_FLIP_HORIZONTAL         0
// Allocate buffers for stills first; live MJPEG remains VGA for smooth streaming.
#define CAMERA_AI_FRAME_SIZE           FRAMESIZE_UXGA
#define CAMERA_LIVE_FRAME_SIZE         FRAMESIZE_VGA

// Private overrides (never commit this file). Board role may also be set with -D BOARD_ROLE=2.
#if __has_include("config.local.h")
#include "config.local.h"
#endif

#endif // CONFIG_H
