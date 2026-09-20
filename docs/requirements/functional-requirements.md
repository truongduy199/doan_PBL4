# Functional Requirements (FR01 - FR10)

- **FR01 Theo dõi ô đỗ**: Giám sát liên tục trạng thái 4 ô đỗ (A1, A2, B1, B2).
- **FR02 Phát hiện xe tại cổng**: Cảm biến quang/tiệm cận phát hiện xe đến cổng vào/ra.
- **FR03 OCR và Khuôn mặt**: Nhận diện chuỗi biển số và trích xuất đặc trưng khuôn mặt tài xế.
- **FR04 Quản lý xe vào**: Cấp phát ô đỗ trống, tạo phiên, mở barie vào.
- **FR05 Quản lý xe ra**: Đối sánh biển số, xác thực khuôn mặt 1:1, đóng phiên, mở barie ra.
- **FR06 Điều khiển thiết bị**: Điều khiển servo barie, LCD hiển thị, còi báo.
- **FR07 Đồng bộ dữ liệu**: Đồng bộ trạng thái ô đỗ và phiên lên Firebase Realtime Database qua Outbox.
- **FR08 Dashboard**: Giám sát trạng thái ô đỗ và phiên hoạt động từ xa.
- **FR09 Xử lý ngoại lệ**: Bắt các trường hợp đỗ sai ô, không nhận diện được, lỗi kết nối.
- **FR10 Xác nhận thủ công**: Cho phép quản trị viên xem xét và duyệt ngoại lệ qua Dashboard.