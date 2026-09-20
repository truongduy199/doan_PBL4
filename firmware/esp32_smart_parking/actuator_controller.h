#ifndef ACTUATOR_CONTROLLER_H
#define ACTUATOR_CONTROLLER_H

void initActuators();
void openEntryBarrier();
void closeEntryBarrier();
void openExitBarrier();
void closeExitBarrier();
void triggerBuzzer(int durationMs);

#endif // ACTUATOR_CONTROLLER_H