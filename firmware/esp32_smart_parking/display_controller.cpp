#include "display_controller.h"
#include "pins.h"
#include "config.example.h"
#include "sensor_manager.h"
#include <Wire.h>
#if BOARD_ROLE == BOARD_ROLE_PLATE_CTRL
#include <U8g2lib.h>
static U8G2_SSD1306_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);
static bool oledReady = false;
static char lastAssignedSlot[12] = "--";
static int backendAvailableSlots = -1;
static unsigned long lastAvailabilityMs = 0;
static char previousRows[5][32] = {};

static const char* shortState(const char* state) {
    if (!state || strcmp(state, "Idle") == 0) return "IDLE";
    if (strcmp(state, "Waiting_backend") == 0) return "WAIT";
    if (strcmp(state, "Open") == 0) return "OPEN";
    if (strcmp(state, "Clear_wait") == 0) return "CLEAR";
    if (strcmp(state, "Closing") == 0) return "CLOSE";
    return "CHECK";
}
static const char* slotLabel(SlotIndex slot) {
    if (!isSlotIrInitialized(slot)) return "?";
    return isSlotIrStableOccupied(slot) ? "OCC" : "FREE";
}
static void renderRows(char rows[5][32]) {
    if (!oledReady || memcmp(rows, previousRows, sizeof(previousRows)) == 0) return;
    memcpy(previousRows, rows, sizeof(previousRows));
    oled.clearBuffer();
    oled.setDrawColor(1);
    oled.setFont(u8g2_font_6x10_tf);
    oled.drawStr(0, 10, rows[0]);
    oled.drawHLine(0, 13, OLED_WIDTH);
    const uint8_t y[] = {25, 37, 49, 62};
    for (int i = 1; i < 5; ++i) oled.drawStr(0, y[i - 1], rows[i]);
    oled.sendBuffer();
}
#endif

bool isDisplayReady() {
#if BOARD_ROLE == BOARD_ROLE_PLATE_CTRL
    return oledReady;
#else
    return false;
#endif
}

void initDisplay() {
#if BOARD_ROLE == BOARD_ROLE_PLATE_CTRL
    Wire.begin(PIN_OLED_SDA, PIN_OLED_SCL);
    Wire.beginTransmission(OLED_I2C_ADDR);
    if (Wire.endTransmission() != 0) {
        Serial.println("[OLED] SSD1306 not detected at configured I2C address");
        return;
    }
    oled.setI2CAddress(OLED_I2C_ADDR << 1);
    oled.setBusClock(100000);
    oled.begin();
    oled.setPowerSave(0);
    oled.setContrast(255);
    oledReady = true;
    displayMessage("PBL4 CONTROL", "Starting...");
#endif
}

void displayMessage(const char* line1, const char* line2) {
#if BOARD_ROLE == BOARD_ROLE_PLATE_CTRL
    char rows[5][32] = {};
    snprintf(rows[0], sizeof(rows[0]), "%.21s", line1 ? line1 : "");
    snprintf(rows[1], sizeof(rows[1]), "%.21s", line2 ? line2 : "");
    renderRows(rows);
#else
    (void)line1; (void)line2;
#endif
}

void updateOledDashboard(const char* gateInStateStr, const char* gateOutStateStr,
                         const char* assignedSlotStr, int availableSlotsCount) {
#if BOARD_ROLE == BOARD_ROLE_PLATE_CTRL
    if (assignedSlotStr && assignedSlotStr[0])
        strlcpy(lastAssignedSlot, assignedSlotStr, sizeof(lastAssignedSlot));
    if (availableSlotsCount >= 0) {
        backendAvailableSlots = availableSlotsCount;
        lastAvailabilityMs = millis();
    }
    int available = millis() - lastAvailabilityMs <= 10000UL ? backendAvailableSlots : -1;
    char rows[5][32] = {};
    snprintf(rows[0], sizeof(rows[0]), "PBL4 CONTROL");
    snprintf(rows[1], sizeof(rows[1]), "IN:%s OUT:%s", shortState(gateInStateStr), shortState(gateOutStateStr));
    snprintf(rows[2], sizeof(rows[2]), "A1:%s A2:%s", slotLabel(SLOT_IDX_A1), slotLabel(SLOT_IDX_A2));
    snprintf(rows[3], sizeof(rows[3]), "B1:%s B2:%s", slotLabel(SLOT_IDX_B1), slotLabel(SLOT_IDX_B2));
    if (available >= 0)
        snprintf(rows[4], sizeof(rows[4]), "AVAIL:%d/4 BAY:%.4s", available, lastAssignedSlot);
    else
        snprintf(rows[4], sizeof(rows[4]), "AVAIL:?/4 BAY:%.4s", lastAssignedSlot);
    renderRows(rows);
#else
    (void)gateInStateStr; (void)gateOutStateStr; (void)assignedSlotStr; (void)availableSlotsCount;
#endif
}
