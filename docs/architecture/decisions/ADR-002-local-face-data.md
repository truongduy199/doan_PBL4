# ADR-002: Lưu mẫu khuôn mặt cục bộ

Mẫu khuôn mặt được mã hóa AES-256-GCM trong MySQL/InnoDB trên laptop, không chuyển xuống ESP hoặc đưa vào dữ liệu giao diện. Ảnh khuôn mặt chỉ giữ trong RAM trong lúc xử lý. SQLite chỉ phục vụ test cô lập.

Thời hạn giữ mẫu phiên và điều kiện xóa được mô tả tại [chính sách dữ liệu](../../database/data-retention.md).
