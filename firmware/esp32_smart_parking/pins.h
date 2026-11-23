#ifndef PINS_H
#define PINS_H

/**
 * Sơ đồ chân chuẩn theo Mục IV.2 & VIII.3 Báo cáo PBL4
 * Board: ESP32-S3 N16R8 CAM (OV5640)
 * Lưu ý quan trọng:
 * - Bỏ hoàn toàn DevKit V1, hai LED xanh/đỏ ngoài và hai điện trở 220 ohm.
 * - Giữ PSRAM (GPIO35-37) cho camera; không dùng microSD và để trống USB-OTG.
 */

// 1. Hai cảm biến IR tại cổng (theo mạch thử: LOW là có vật)
#define PIN_IR_GATE_IN     1
#define PIN_IR_GATE_OUT    2

// 2. Bốn cảm biến IR tại bốn ô đỗ A1, A2, B1, B2 (theo mạch thử: LOW là có vật)
#define PIN_IR_SLOT_A1     14
#define PIN_IR_SLOT_A2     21
#define PIN_IR_SLOT_B1     41
#define PIN_IR_SLOT_B2     42

// 3. Hai Servo Barie (PWM 50Hz, dùng LEDC Timer 1, Kênh 2 & 3, 14-bit để tránh trùng Timer 0 của Camera)
#define PIN_SERVO_IN       38
#define PIN_SERVO_OUT      39


// 5. Màn hình OLED SSD1306 128x64 I2C (Địa chỉ 0x3C)
#define PIN_OLED_SDA       40
#define PIN_OLED_SCL       47
#define OLED_I2C_ADDR      0x3C
#define OLED_WIDTH         128
#define OLED_HEIGHT        64

// 6. Chân Camera OV5640 trên bo ESP32-S3 N16R8 CAM chuẩn (Dành riêng Timer 0 / Channel 0 cho XCLK)
#define CAM_PIN_PWDN       -1
#define CAM_PIN_RESET      -1
#define CAM_PIN_XCLK       15
#define CAM_PIN_SIOD       4
#define CAM_PIN_SIOC       5
#define CAM_PIN_D7         16
#define CAM_PIN_D6         17
#define CAM_PIN_D5         18
#define CAM_PIN_D4         12
#define CAM_PIN_D3         10
#define CAM_PIN_D2         8
#define CAM_PIN_D1         9
#define CAM_PIN_D0         11
#define CAM_PIN_VSYNC      6
#define CAM_PIN_HREF       7
#define CAM_PIN_PCLK       13

#endif // PINS_H
