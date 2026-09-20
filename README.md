# Smart Parking PBL4 - Hệ thống Bãi đỗ xe thông minh

Dự án Đồ án Chuyên ngành Công nghệ Thông tin (PBL4) - Trường Đại học Bách khoa, Đại học Đà Nẵng.

## Kiến trúc Hệ thống Monorepo

- **Edge Server (edge-server/)**: Python 3.10+, trung tâm xử lý AI (InsightFace, OCR biển số, theo dõi ô đỗ xe), máy trạng thái quản lý phiên vào/ra, cơ sở dữ liệu SQLite cục bộ, và đồng bộ dữ liệu lên Firebase.
- **Firmware (irmware/)**: Mã nguồn ESP32 điều khiển cảm biến tiệm cận/quang, điều khiển servo barie, màn hình LCD hiển thị và còi buzzer; giao tiếp qua Serial giao thức tin cậy (ACK/Event ID).
- **Dashboard (dashboard/)**: Giao diện giám sát Web quản trị viên xây dựng trên React, TypeScript và Vite; kết nối Firebase Realtime Database.
- **Contracts (contracts/)**: Định nghĩa schema giao thức Serial, Firebase và các trạng thái chuẩn hóa.
- **Firebase (irebase/)**: Cấu hình Firebase Realtime Database rules, indexes, storage rules.
- **Docs (docs/)**: Tài liệu phân tích yêu cầu (FR/NFR), kiến trúc ADR, sơ đồ tuần tự, tài liệu giao thức.
- **Evaluation (evaluation/)**: Bộ công cụ đo lường hiệu năng, TAR/FAR khuôn mặt, độ chính xác OCR và Occupancy.
- **System Tests (system-tests/)**: Kịch bản kiểm thử toàn trình từ đầu vào đến đầu ra.

Xem chi tiết kiến trúc tại [Cau_truc_du_an_PBL4.md](Cau_truc_du_an_PBL4.md).

Thành viên mới xem hướng dẫn cài đặt và quy trình làm việc tại [HUONG_DAN_SETUP_THANH_VIEN.md](HUONG_DAN_SETUP_THANH_VIEN.md).
