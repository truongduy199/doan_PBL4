#include "actuator_controller.h"
#include "pins.h"
#include <Arduino.h>

void initActuators() {
    pinMode(PIN_BUZZER, OUTPUT);
}

void openEntryBarrier() {}
void closeEntryBarrier() {}
void openExitBarrier() {}
void closeExitBarrier() {}
void triggerBuzzer(int durationMs) {}