# ADR-003: Ngừng dùng đồng bộ Firebase

Đề xuất Outbox/SQLite/Firebase cũ đã được thay thế bằng MySQL trên laptop và FastAPI REST, WebSocket/SSE. Firmware dùng MQTT cho sự kiện/lệnh và HTTP cho ảnh. Mã Firebase và contracts tương ứng đã được loại khỏi source.

Xem [kiến trúc hiện hành](../../diagrams/architecture.mmd) và [hướng dẫn tích hợp](../../setup/system-integration.md).
