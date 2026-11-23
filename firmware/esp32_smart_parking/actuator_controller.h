#ifndef ACTUATOR_CONTROLLER_H
#define ACTUATOR_CONTROLLER_H

#include <Arduino.h>

void initActuators();

void openEntryBarrier();
void closeEntryBarrier();
void openExitBarrier();
void closeExitBarrier();

bool isEntryBarrierOpenCommanded();
bool isExitBarrierOpenCommanded();


#endif // ACTUATOR_CONTROLLER_H
