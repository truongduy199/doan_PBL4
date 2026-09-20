#include "sensor_manager.h"
#include "pins.h"
#include <Arduino.h>

void initSensors() {
    pinMode(PIN_ENTRY_SENSOR_1, INPUT);
    pinMode(PIN_ENTRY_SENSOR_2, INPUT);
    pinMode(PIN_EXIT_SENSOR_1, INPUT);
    pinMode(PIN_EXIT_SENSOR_2, INPUT);
}

void updateSensors() {
    // Đọc và lọc nhiễu tín hiệu cảm biến
}