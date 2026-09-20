/**
 * Smart Parking PBL4 - ESP32 Firmware Main Sketch
 * Board: ESP32 Dev Module
 */

#include "pins.h"
#include "protocol.h"
#include "gate_state_machine.h"
#include "sensor_manager.h"
#include "actuator_controller.h"
#include "display_controller.h"
#include "serial_transport.h"

void setup() {
    Serial.begin(115200);
    initSensors();
    initActuators();
    initDisplay();
    displayMessage("SMART PARKING", "SAN SANG...");
}

void loop() {
    updateSensors();
    handleSerialMessages();
    updateGateStateMachine();
}