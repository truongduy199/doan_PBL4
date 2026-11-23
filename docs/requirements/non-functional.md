# Non-Functional Requirements (NFR)

1. **Hiệu năng & Độ trễ**: Thời gian từ khi xe kích hoạt cảm biến đến khi mở barie <= 2.5s.
2. **Độ chính xác xác thực**: TAR >= 95% tại FAR <= 0.1% với InsightFace Buffalo_L.
3. **Bảo mật & Quyền riêng tư**: Face embeddings được mã hóa lưu cục bộ, xóa sau 24h. Không tải ảnh mặt lên cloud.
4. **Độ tin cậy ngoại tuyến**: Hệ thống cần vận hành trong LAN khi mất Internet, với frontend đã build và model có sẵn. Mất Wi-Fi, MQTT hoặc MySQL phải được xử lý riêng; không tự cấp quyền mở barie khi chưa xác minh được trạng thái.

Các chỉ tiêu hiệu năng và độ chính xác trên là mục tiêu nghiệm thu, chưa phải kết quả đã đo trên phần cứng thật.
