# Bảng đấu nối theo kiến trúc hai ESP32-S3

Bảng này chép theo cấu hình phần mềm hiện hành, chưa thay cho việc đối chiếu pinout chính xác của bo N16R8 CAM thực tế. Hai bo cùng dùng camera OV5640 có sẵn trên bo. Chỉ bo biển số kiêm điều khiển nối các ngoại vi bên dưới.

| Tín hiệu | GPIO |
| --- | --- |
| IR cổng IN / OUT | 1 / 2 |
| IR A1 / A2 / B1 / B2 | 14 / 21 / 41 / 42 |
| Servo IN / OUT | 38 / 39 |
| OLED SDA / SCL | 40 / 47 |
| OLED địa chỉ / kích thước | 0x3C / 128×64 |
| Camera XCLK / SCCB SDA / SCCB SCL | 15 / 4 / 5 |
| Camera D0..D7 | 11, 9, 8, 10, 12, 18, 17, 16 |
| Camera VSYNC / HREF / PCLK | 6 / 7 / 13 |

PSRAM OPI giữ GPIO35–37, không dùng microSD. GPIO19/20 không dùng cho ngoại vi; bo điều khiển bật USB Serial/JTAG để đọc log khởi động (`ARDUINO_USB_MODE=1`, `ARDUINO_USB_CDC_ON_BOOT=1`). Bo khuôn mặt giữ cấu hình USB riêng trong môi trường build. Servo dùng LEDC timer 1 (kênh 2/3), camera dùng timer 0/kênh 0. OLED dùng I2C0; thư viện camera của toolchain hiện dùng I2C1 cho SCCB.

Hai servo dùng nguồn 5V ngoài đủ dòng và chung GND với S3 điều khiển; không kéo dòng servo từ chân 3V3. Mỗi S3 cấp nguồn riêng phù hợp. Tín hiệu vào GPIO phải trong mức cho phép của S3: đo ngõ OUT của IR và kiểm tra cách cấp nguồn trước khi nối; không mặc định module cấp 5V thì OUT an toàn cho 3V3.

Không có ESP32 DevKit V1, hai LED ngoài hoặc hai điện trở 220Ω trong phương án này. Sơ đồ Wokwi hiện hành: https://wokwi.com/projects/481261560534933505. Mô phỏng không xác minh camera, nguồn servo hay mức điện áp thực.

Quy trình build, cấu hình và phần chưa kiểm chứng: [system-integration.md](system-integration.md).

Servo dùng xung 1000–2000 µs, đóng 0° và mở 170° theo bản test phần cứng. OLED dùng U8g2 SSD1306 128×64, hướng R0, font 6×10 và tương phản 255. Không còn mã điều khiển còi.
