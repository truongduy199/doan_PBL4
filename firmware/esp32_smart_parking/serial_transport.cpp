#include "serial_transport.h"
#include "config.example.h"
#include "sensor_manager.h"
#include "gate_state_machine.h"
#include "protocol.h"
#include <Arduino.h>

void handleSerialMessages() {
#if ENABLE_WOKWI_SERIAL_SIM && (BOARD_ROLE == BOARD_ROLE_PLATE_CTRL)
    while (Serial.available() > 0) {
        char c = (char)Serial.read();
        if (c == '\r' || c == '\n' || c == ' ') {
            continue;
        }
        if (c == 'i' || c == 'I') {
            String reason;
            bool ok = simulateWokwiSerialApprove(GATE_IDX_IN, reason);
            Serial.printf("[WOKWI-SIM] Lenh 'i' (Gate IN): ok=%d, reason=%s\n", ok ? 1 : 0, reason.c_str());
        } else if (c == 'o' || c == 'O') {
            String reason;
            bool ok = simulateWokwiSerialApprove(GATE_IDX_OUT, reason);
            Serial.printf("[WOKWI-SIM] Lenh 'o' (Gate OUT): ok=%d, reason=%s\n", ok ? 1 : 0, reason.c_str());
        } else if (c == 's' || c == 'S') {
            publishSlotsSnapshot(true);
            publishDeviceHeartbeat();
        }
    }
#endif
}
