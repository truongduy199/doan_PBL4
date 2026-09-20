# Non-Functional Requirements (NFR)

1. **Hiệu năng & Độ trễ**: Thời gian từ khi xe kích hoạt cảm biến đến khi mở barie <= 2.5s.
2. **Độ chính xác xác thực**: TAR >= 95% tại FAR <= 0.1% với InsightFace Buffalo_L.
3. **Bảo mật & Quyền riêng tư**: Face embeddings được mã hóa lưu cục bộ, xóa sau 24h. Không tải ảnh mặt lên cloud.
4. **Độ tin cậy ngoại tuyến**: Mất Internet hệ thống vẫn hoạt động cục bộ 100% và tự đồng bộ khi có mạng lại.