#include "sensor_manager.h"
#include "pins.h"
#include "config.example.h"

static DebouncedSensor gateSensors[GATE_COUNT] = {
    {PIN_IR_GATE_IN,  "IR_GATE_IN",  "IN",  HIGH, false, false, false, 0, GATE_IR_FILTER_MS},
    {PIN_IR_GATE_OUT, "IR_GATE_OUT", "OUT", HIGH, false, false, false, 0, GATE_IR_FILTER_MS}
};

static DebouncedSensor slotSensors[SLOT_COUNT] = {
    {PIN_IR_SLOT_A1, "IR_A1", "A1", HIGH, false, false, false, 0, SLOT_IR_STABLE_MS},
    {PIN_IR_SLOT_A2, "IR_A2", "A2", HIGH, false, false, false, 0, SLOT_IR_STABLE_MS},
    {PIN_IR_SLOT_B1, "IR_B1", "B1", HIGH, false, false, false, 0, SLOT_IR_STABLE_MS},
    {PIN_IR_SLOT_B2, "IR_B2", "B2", HIGH, false, false, false, 0, SLOT_IR_STABLE_MS}
};

static bool slotStateChangedFlag = false;

static void updateSingleSensor(DebouncedSensor& s, unsigned long nowMs, bool isSlotSensor) {
    int level = digitalRead(s.pin);
    s.rawLevel = level;
    bool detectedNow = (level == IR_ACTIVE_STATE);

    if (detectedNow != s.candidateDetected) {
        s.candidateDetected = detectedNow;
        s.lastChangeMs = nowMs;
    }

    if ((nowMs - s.lastChangeMs) >= s.debounceWindowMs) {
        if (!s.isInitialized || s.stableDetected != s.candidateDetected) {
            s.stableDetected = s.candidateDetected;
            s.isInitialized = true;
            if (isSlotSensor) {
                slotStateChangedFlag = true;
            }
        }
    }
}

void initSensors() {
#if (BOARD_ROLE == BOARD_ROLE_PLATE_CTRL)
    unsigned long nowMs = millis();
    for (int i = 0; i < GATE_COUNT; ++i) {
        pinMode(gateSensors[i].pin, INPUT_PULLUP);
        gateSensors[i].rawLevel = digitalRead(gateSensors[i].pin);
        gateSensors[i].candidateDetected = (gateSensors[i].rawLevel == IR_ACTIVE_STATE);
        gateSensors[i].stableDetected = gateSensors[i].candidateDetected;
        gateSensors[i].isInitialized = false; // Chờ đủ cửa sổ lọc mới công bố
        gateSensors[i].lastChangeMs = nowMs;
    }
    for (int i = 0; i < SLOT_COUNT; ++i) {
        pinMode(slotSensors[i].pin, INPUT_PULLUP);
        slotSensors[i].rawLevel = digitalRead(slotSensors[i].pin);
        slotSensors[i].candidateDetected = (slotSensors[i].rawLevel == IR_ACTIVE_STATE);
        slotSensors[i].stableDetected = false;
        // Mục III.2: Khi khởi động, trạng thái ô là Unknown cho đến khi nhận đủ dữ liệu hợp lệ và ổn định
        slotSensors[i].isInitialized = false;
        slotSensors[i].lastChangeMs = nowMs;
    }
#endif
}

void updateSensors() {
#if (BOARD_ROLE == BOARD_ROLE_PLATE_CTRL)
    unsigned long nowMs = millis();
    for (int i = 0; i < GATE_COUNT; ++i) {
        updateSingleSensor(gateSensors[i], nowMs, false);
    }
    for (int i = 0; i < SLOT_COUNT; ++i) {
        updateSingleSensor(slotSensors[i], nowMs, true);
    }
#endif
}

bool isGateIrStableDetected(GateIndex gate) {
    if (gate < 0 || gate >= GATE_COUNT) return false;
    return gateSensors[gate].isInitialized && gateSensors[gate].stableDetected;
}

int getGateIrRawLevel(GateIndex gate) {
    if (gate < 0 || gate >= GATE_COUNT) return HIGH;
    return gateSensors[gate].rawLevel;
}

bool isSlotIrInitialized(SlotIndex slot) {
    if (slot < 0 || slot >= SLOT_COUNT) return false;
    return slotSensors[slot].isInitialized;
}

bool isSlotIrStableOccupied(SlotIndex slot) {
    if (slot < 0 || slot >= SLOT_COUNT) return false;
    return slotSensors[slot].isInitialized && slotSensors[slot].stableDetected;
}

int getSlotIrRawLevel(SlotIndex slot) {
    if (slot < 0 || slot >= SLOT_COUNT) return HIGH;
    return slotSensors[slot].rawLevel;
}

const char* getSlotIdName(SlotIndex slot) {
    if (slot < 0 || slot >= SLOT_COUNT) return "UNK";
    return slotSensors[slot].slotOrGateId;
}

const char* getSlotSensorIdName(SlotIndex slot) {
    if (slot < 0 || slot >= SLOT_COUNT) return "UNK";
    return slotSensors[slot].id;
}

const char* getSlotPhysicalStatusString(SlotIndex slot) {
    if (slot < 0 || slot >= SLOT_COUNT) return "Unknown";
    if (!slotSensors[slot].isInitialized) {
        return "Unknown";
    }
    return slotSensors[slot].stableDetected ? "Occupied" : "Free";
}

bool consumeSlotStateChangedFlag() {
    bool changed = slotStateChangedFlag;
    slotStateChangedFlag = false;
    return changed;
}

uint8_t countLocalFreeSlots() {
    uint8_t count = 0;
    for (int i = 0; i < SLOT_COUNT; ++i) {
        if (slotSensors[i].isInitialized && !slotSensors[i].stableDetected) {
            count++;
        }
    }
    return count;
}
