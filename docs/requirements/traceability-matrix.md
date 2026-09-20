# Traceability Matrix

| FR ID | Tên yêu cầu | Module Edge | Firmware ESP32 | Test Case |
|---|---|---|---|---|
| FR01 | Theo dõi ô đỗ | `ai/parking` | - | `TC_PARK_01` |
| FR02 | Phát hiện xe tại cổng | `infrastructure/serial` | `sensor_manager` | `TC_GATE_01` |
| FR03 | OCR & Khuôn mặt | `ai/plate`, `ai/face` | - | `TC_AI_01` |
| FR04 | Quản lý xe vào | `workflows/vehicle_entry` | `gate_state_machine` | `TC_ENTRY_01` |
| FR05 | Quản lý xe ra | `workflows/vehicle_exit` | `gate_state_machine` | `TC_EXIT_01` |