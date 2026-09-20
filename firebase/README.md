# Firebase Configuration & Security Rules

Cấu hình cho Firebase Realtime Database và Cloud Storage:
- `database.rules.json`: Phân quyền đọc/ghi. Edge Server dùng Service Account Admin có toàn quyền ghi; Dashboard chỉ ghi vào `review_requests`.
- `storage.rules`: Chỉ cho phép upload ảnh chụp biển số xe, cấm ảnh khuôn mặt.
- `emulator-seed/database.json`: Khởi tạo sẵn 4 ô đỗ `A1`, `A2`, `B1`, `B2` cho Firebase Local Emulator.