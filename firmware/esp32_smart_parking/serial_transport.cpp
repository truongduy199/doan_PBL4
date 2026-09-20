#include "serial_transport.h"
#include <Arduino.h>

void handleSerialMessages() {
    if (Serial.available()) {
        String line = Serial.readStringUntil('\n');
        line.trim();
        // Xử lý chuỗi nhận được
    }
}