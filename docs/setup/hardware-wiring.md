# Bảng đấu nối theo kiến trúc hai ESP32-S3

Bảng này chép theo cấu hình phần mềm hiện hành, chưa thay cho việc đối chiếu pinout chính xác của bo N16R8 CAM thực tế. Hai bo cùng dùng camera OV5640 có sẵn trên bo. Chỉ bo biển số kiêm điều khiển nối các ngoại vi bên dưới.

| Tín hiệu | GPIO |
| --- | --- |
| IR cổng IN / OUT | 1 / 2 |
| IR A1 / A2 / B1 / B2 | 14 / 21 / 41 / 42 |
| Servo IN / OUT | 38 / 39 |
| Còi MH-FMD, active LOW | 20 |
| OLED SDA / SCL | 40 / 47 |
| OLED địa chỉ / kích thước | 0x3C / 128×64 |
| Camera XCLK / SCCB SDA / SCCB SCL | 15 / 4 / 5 |
| Camera D0..D7 | 11, 9, 8, 10, 12, 18, 17, 16 |
| Camera VSYNC / HREF / PCLK | 6 / 7 / 13 |

PSRAM OPI giữ GPIO35–37, không dùng microSD. GPIO20 dùng còi nên USB native/USB CDC tắt; nạp/debug bằng USB-UART của bo. Servo dùng LEDC timer 1 (kênh 2/3), camera dùng timer 0/kênh 0.

Hai servo dùng nguồn 5V ngoài đủ dòng và chung GND với S3 điều khiển; không kéo dòng servo từ chân 3V3. Mỗi S3 cấp nguồn riêng phù hợp. Tín hiệu vào GPIO phải trong mức cho phép của S3: đo ngõ OUT của IR và kiểm tra cách cấp nguồn trước khi nối; không mặc định module cấp 5V thì OUT an toàn cho 3V3.

Không có ESP32 DevKit V1, hai LED ngoài hoặc hai điện trở 220Ω trong phương án này. Sơ đồ Wokwi hiện hành: https://wokwi.com/projects/481261560534933505. Mô phỏng không xác minh camera, nguồn servo hay mức điện áp thực.

Quy trình build, cấu hình và phần chưa kiểm chứng: [duy-handover.md](duy-handover.md).
