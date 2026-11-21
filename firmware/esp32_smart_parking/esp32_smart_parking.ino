/**
 * Smart Parking PBL4 - ESP32-S3 N16R8 OV5640 Firmware
 *
 * Kiến trúc phần cứng đã chốt (Mục IV & VIII Báo cáo PBL4):
 * - Chỉ sử dụng 2 bo ESP32-S3 N16R8 gắn camera OV5640 (Bỏ bo DevKit V1, bỏ 2 LED xanh/đỏ ngoài và 2 điện trở 220 ohm):
 *   1. Bo S3 biển số kiêm điều khiển (BOARD_ROLE = BOARD_ROLE_PLATE_CTRL):
 *      - Chụp ảnh biển số IN/OUT gửi JPEG qua HTTP POST /api/device/images.
 *      - Đọc & lọc nhiễu 6 cảm biến IR: 2 IR cổng (GPIO1, GPIO2) + 4 IR ô đỗ A1..B2 (GPIO14, GPIO21, GPIO41, GPIO42).
 *      - Điều khiển 2 Servo Barie (GPIO38, GPIO39 - LEDC Timer 1, Kênh 2/3, 14-bit), OLED SSD1306 I2C (SDA=40, SCL=47) và Còi MH-FMD (GPIO20).
 *      - Chạy máy trạng thái 2 cổng độc lập (Idle -> Waiting_backend -> Open -> Clear_wait 3s -> Closing / Review_required).
 *   2. Bo S3 khuôn mặt độc lập (BOARD_ROLE = BOARD_ROLE_FACE_CAM):
 *      - Nhận yêu cầu chụp MQTT `parking/cameras/face/capture` và gửi ảnh JPEG qua HTTP POST /api/device/images.
 */

#include "config.example.h"
#include "pins.h"
#include "sensor_manager.h"
#include "actuator_controller.h"
#include "display_controller.h"
#include "gate_state_machine.h"
#include "protocol.h"
#include "serial_transport.h"

void setup() {
    // Dùng UART0 chuẩn cho debug/Wokwi, giữ GPIO20 làm chân điều khiển còi MH-FMD (tránh USB native trên GPIO20)
    Serial.begin(SERIAL_BAUD);
    delay(200);

    Serial.println("====================================================");
    Serial.println("PBL4 SMART PARKING - ESP32-S3 N16R8 OV5640 FIRMWARE");
    Serial.printf("Device ID: %s | Camera ID: %s\n", DEVICE_ID, CAMERA_ID);
    Serial.println("====================================================");

    initSensors();
    initActuators();
    initDisplay();
    initGateStateMachine();
    initNetworkAndProtocol();
}

void loop() {
    // Toàn bộ các bước đều không chặn (non-blocking) để truyền ảnh/MQTT không làm trễ đọc IR hoặc máy trạng thái cổng
    updateSensors();
    updateGateStateMachine();
    updateActuators();
    updateNetworkAndProtocol();
    handleSerialMessages();
    delay(1); // Yield to the network worker; no HTTP/MQTT runs in this control loop.
}
