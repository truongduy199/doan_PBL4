#ifndef SERIAL_TRANSPORT_H
#define SERIAL_TRANSPORT_H

/**
 * Kênh Serial0 UART chỉ phục vụ:
 * 1. Nạp code / in log chẩn đoán (debug).
 * 2. Nhận phím giả lập 'i' (cấp phép cổng IN) / 'o' (cấp phép cổng OUT) / 's' (in trạng thái) trên mạch mô phỏng Wokwi.
 * Lưu ý (Mục IV.2 & IV.3): Tuyệt đối KHÔNG dùng Serial USB làm kênh giao tiếp vận hành với laptop.
 */
void handleSerialMessages();

#endif // SERIAL_TRANSPORT_H
