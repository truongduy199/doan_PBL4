#ifndef SENSOR_MANAGER_H
#define SENSOR_MANAGER_H

#include <Arduino.h>

enum GateIndex {
    GATE_IDX_IN = 0,
    GATE_IDX_OUT = 1,
    GATE_COUNT = 2
};

enum SlotIndex {
    SLOT_IDX_A1 = 0,
    SLOT_IDX_A2 = 1,
    SLOT_IDX_B1 = 2,
    SLOT_IDX_B2 = 3,
    SLOT_COUNT = 4
};

struct DebouncedSensor {
    uint8_t pin;
    const char* id;
    const char* slotOrGateId;
    int rawLevel;
    bool candidateDetected;
    bool stableDetected;
    bool isInitialized;
    unsigned long lastChangeMs;
    unsigned long debounceWindowMs;
};

void initSensors();
void updateSensors();

// Trạng thái 2 cảm biến IR cổng (IN, OUT)
bool isGateIrStableDetected(GateIndex gate);
int getGateIrRawLevel(GateIndex gate);

// Trạng thái 4 cảm biến IR ô đỗ (A1, A2, B1, B2)
bool isSlotIrInitialized(SlotIndex slot);
bool isSlotIrStableOccupied(SlotIndex slot);
int getSlotIrRawLevel(SlotIndex slot);
const char* getSlotIdName(SlotIndex slot);
const char* getSlotSensorIdName(SlotIndex slot);
const char* getSlotPhysicalStatusString(SlotIndex slot);

// Cờ báo có sự thay đổi trạng thái ổn định của 1 trong 4 ô đỗ để gửi snapshot ngay
bool consumeSlotStateChangedFlag();
uint8_t countLocalFreeSlots();

#endif // SENSOR_MANAGER_H
