#ifndef DISPLAY_CONTROLLER_H
#define DISPLAY_CONTROLLER_H

#include <Arduino.h>

void initDisplay();
bool isDisplayReady();
void displayMessage(const char* line1, const char* line2);
void updateOledDashboard(
    const char* gateInStateStr,
    const char* gateOutStateStr,
    const char* assignedSlotStr,
    int availableSlotsCount
);

#endif // DISPLAY_CONTROLLER_H
