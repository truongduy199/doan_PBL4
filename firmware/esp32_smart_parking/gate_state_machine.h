#ifndef GATE_STATE_MACHINE_H
#define GATE_STATE_MACHINE_H

#include <Arduino.h>
#include "sensor_manager.h"

/**
 * Máy trạng thái 2 Barie độc lập (IN & OUT) theo đúng Mục IV.9 Báo cáo PBL4:
 * Các trạng thái chuẩn:
 * - Idle
 * - Waiting_backend
 * - Open
 * - Clear_wait
 * - Closing
 * - Review_required
 */
enum GateState {
    GATE_STATE_IDLE = 0,
    GATE_STATE_WAITING_BACKEND,
    GATE_STATE_OPEN,
    GATE_STATE_CLEAR_WAIT,
    GATE_STATE_CLOSING,
    GATE_STATE_REVIEW_REQUIRED
};

struct GateContext {
    GateIndex gateIndex;
    const char* gateId;         // "IN" hoặc "OUT"
    GateState state;
    char currentEventId[40];    // event_id của lượt hiện hành
    char lastCommandId[40];     // command_id đã thực thi để chống lặp lệnh MQTT
    char assignedSlotId[12];    // Ô được cấp (để hiển thị lên OLED)
    unsigned long stateEnteredMs;
    unsigned long clearStartedMs;
    bool passageReported;
};

void initGateStateMachine();
void updateGateStateMachine();

const GateContext& getGateContext(GateIndex gate);
const char* gateStateToString(GateState state);

// Xử lý lệnh điều khiển từ Backend qua MQTT (parking/gates/IN/command, parking/gates/OUT/command)
bool applyBackendGateCommand(
    const char* gateId,
    const char* commandId,
    const char* eventId,
    const char* action,
    const char* assignedSlotId,
    long expiresInMs,
    String& outReason
);

// Giả lập cấp phép qua Serial ('i' cho IN, 'o' cho OUT) trên Wokwi theo Mục IV.2 & VIII.3
bool simulateWokwiSerialApprove(GateIndex gate, String& outReason);

#endif // GATE_STATE_MACHINE_H
