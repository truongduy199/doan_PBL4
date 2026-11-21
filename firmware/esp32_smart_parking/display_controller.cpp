#include "display_controller.h"
#include "pins.h"
#include "config.example.h"
#include "sensor_manager.h"
#include <Wire.h>

#if __has_include(<Adafruit_GFX.h>) && __has_include(<Adafruit_SSD1306.h>)
#define HAS_ADAFRUIT_SSD1306 1
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
static Adafruit_SSD1306 oled(OLED_WIDTH, OLED_HEIGHT, &Wire, -1);
#else
#define HAS_ADAFRUIT_SSD1306 0
#endif

static bool oledReady = false;
static char lastAssignedSlot[12] = "--";
static int backendAvailableSlots = -1; // -1 nghĩa là hiển thị tạm số ô trống đo cục bộ
static unsigned long lastAvailabilityMs = 0;

void initDisplay() {
#if (BOARD_ROLE == BOARD_ROLE_PLATE_CTRL)
    Wire.begin(PIN_OLED_SDA, PIN_OLED_SCL);
#if HAS_ADAFRUIT_SSD1306
    if (oled.begin(SSD1306_SWITCHCAPVCC, OLED_I2C_ADDR)) {
        oledReady = true;
        oled.clearDisplay();
        oled.setTextColor(SSD1306_WHITE);
        oled.setTextSize(1);
        oled.setCursor(0, 0);
        oled.println("PBL4 SMART PARKING");
        oled.println("ESP32-S3 OV5640");
        oled.display();
    }
#endif
#endif
}

void displayMessage(const char* line1, const char* line2) {
#if (BOARD_ROLE == BOARD_ROLE_PLATE_CTRL)
#if HAS_ADAFRUIT_SSD1306
    if (!oledReady) return;
    oled.clearDisplay();
    oled.setTextSize(1);
    oled.setCursor(0, 0);
    oled.println(line1 ? line1 : "");
    oled.setCursor(0, 16);
    oled.println(line2 ? line2 : "");
    oled.display();
#else
    (void)line1;
    (void)line2;
#endif
#endif
}

void updateOledDashboard(
    const char* gateInStateStr,
    const char* gateOutStateStr,
    const char* assignedSlotStr,
    int availableSlotsCount
) {
#if (BOARD_ROLE == BOARD_ROLE_PLATE_CTRL)
    if (assignedSlotStr && assignedSlotStr[0] != '\0') {
        strncpy(lastAssignedSlot, assignedSlotStr, sizeof(lastAssignedSlot) - 1);
        lastAssignedSlot[sizeof(lastAssignedSlot) - 1] = '\0';
    }
    if (availableSlotsCount >= 0) {
        backendAvailableSlots = availableSlotsCount;
        lastAvailabilityMs = millis();
    }
    int avail = (millis() - lastAvailabilityMs <= 10000UL) ? backendAvailableSlots : -1;

#if HAS_ADAFRUIT_SSD1306
    if (!oledReady) return;
    oled.clearDisplay();
    oled.setTextSize(1);

    // Dòng 1: Số ô có thể nhận xe & Ô vừa được cấp (Mục IV.1 & VI)
    oled.setCursor(0, 0);
    if (avail >= 0) oled.printf("Nhan xe:%d/4 | O:%s", avail, lastAssignedSlot);
    else oled.printf("Nhan xe:?/4 | O:%s", lastAssignedSlot);

    // Dòng 2: Trạng thái 4 cảm biến IR ô đỗ A1, A2, B1, B2
    oled.setCursor(0, 14);
    oled.printf(
        "A1:%c A2:%c B1:%c B2:%c",
        isSlotIrInitialized(SLOT_IDX_A1) ? (isSlotIrStableOccupied(SLOT_IDX_A1) ? 'X' : '_') : '?',
        isSlotIrInitialized(SLOT_IDX_A2) ? (isSlotIrStableOccupied(SLOT_IDX_A2) ? 'X' : '_') : '?',
        isSlotIrInitialized(SLOT_IDX_B1) ? (isSlotIrStableOccupied(SLOT_IDX_B1) ? 'X' : '_') : '?',
        isSlotIrInitialized(SLOT_IDX_B2) ? (isSlotIrStableOccupied(SLOT_IDX_B2) ? 'X' : '_') : '?'
    );

    // Dòng 3: Trạng thái Cổng IN
    oled.setCursor(0, 30);
    oled.printf("IN : %s", gateInStateStr ? gateInStateStr : "Idle");

    // Dòng 4: Trạng thái Cổng OUT
    oled.setCursor(0, 44);
    oled.printf("OUT: %s", gateOutStateStr ? gateOutStateStr : "Idle");

    oled.display();
#else
    (void)gateInStateStr;
    (void)gateOutStateStr;
    (void)avail;
#endif
#endif
}
