#ifndef ACTUATOR_CONTROLLER_H
#define ACTUATOR_CONTROLLER_H

#include <Arduino.h>

void initActuators();
void updateActuators();

void openEntryBarrier();
void closeEntryBarrier();
void openExitBarrier();
void closeExitBarrier();

bool isEntryBarrierOpenCommanded();
bool isExitBarrierOpenCommanded();

// Còi MH-FMD không chặn vòng lặp (non-blocking)
void triggerBuzzer(unsigned long durationMs);
void triggerBuzzerPattern(uint8_t beeps, unsigned long onMs, unsigned long offMs);

#endif // ACTUATOR_CONTROLLER_H
