# Đối chiếu yêu cầu và mã nguồn

| FR | Chức năng | Backend | Firmware / frontend | Kiểm chứng |
| --- | --- | --- | --- | --- |
| FR01 | Trạng thái 4 ô đỗ từ IR | `GateDataService`, `SlotService` | `sensor_manager.cpp`, giao diện User/Admin | `test_system_acceptance.py` (T02, snapshot, sai ô) |
| FR02 | Phát hiện xe tại cổng | `MqttGateBridge`, `GateWorkflowService` | `gate_state_machine.cpp`, `protocol.cpp` | `test_gate_runtime.py`; cần thử IR thật |
| FR03 | Biển số, khuôn mặt và liveness | `ai/plate`, `ai/face`, `modules/license_plate_yolo_numpy` | Hai camera OV5640 gửi HTTP JPEG | Test AI integration; độ chính xác cần đo riêng |
| FR04 | Xe vào và cấp ô | `GateWorkflowService`, `GateDataService` | State machine cổng IN | Test runtime và acceptance T01, T07 |
| FR05 | Xe ra và xác thực phiên | `GateWorkflowService`, `GateDataService` | State machine cổng OUT | Test runtime và acceptance T08, T15 |
| FR06 | Servo, OLED, còi | MQTT command / ACK | `actuator_controller.cpp`, `display_controller.cpp` | Cần kiểm chứng trên bo thật |
| FR07 | Cập nhật realtime trong LAN | MQTT, MySQL, REST, WebSocket/SSE | Các API service của React | Test runtime và REST integration |
| FR08 | Web User và Admin | HTTP auth, slots, bookings, admin | `App.tsx`, `UserBookingPortal`, `AdminDashboardPage` | Test acceptance phân quyền / riêng tư; build Vite |
| FR09 | Timeout, mất kết nối, sai ô | `GateWorkflowService`, `GateDataService` | Kiểm tra hạn lệnh và IR | `test_gate_runtime.py`, test acceptance sai ô |
| FR10 | Duyệt thủ công | HTTP admin và `GateWorkflowService` | Admin Dashboard | Test acceptance manual review và chống lặp |

Các file test nằm trong `edge-server/tests/`. Test cô lập không thay cho đo GPIO, hiệu năng InnoDB hoặc đánh giá AI trên dữ liệu thực.
