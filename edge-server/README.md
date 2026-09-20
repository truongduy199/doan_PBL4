# Edge Server - Smart Parking PBL4

Thành phần trung tâm của hệ thống Smart Parking, đảm nhiệm:
1. Nhận diện biển số xe (OCR).
2. Trích xuất và xác thực khuôn mặt 1:1 bằng InsightFace.
3. Giám sát trạng thái 4 ô đỗ qua camera toàn cảnh.
4. Điều khiển logic vào/ra qua máy trạng thái (State Machine).
5. Giao tiếp hai chiều với ESP32 qua Serial (giao thức tin cậy ACK/checksum).
6. Quản lý cơ sở dữ liệu SQLite cục bộ và hàng đợi outbox đồng bộ Firebase.