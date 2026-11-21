#include "gate_state_machine.h"
#include "config.example.h"
#include "actuator_controller.h"
#include "display_controller.h"
#include "protocol.h"

static GateContext gates[GATE_COUNT];
static uint32_t eventCounter = 0;

static void generateEventId(const char* gateId, char* outBuf, size_t bufSize) {
    eventCounter++;
    snprintf(outBuf, bufSize, "ev-%s-%s-%08lx-%08lx", getBootId(), gateId, (unsigned long)millis(), (unsigned long)eventCounter);
}

const char* gateStateToString(GateState state) {
    switch (state) {
        case GATE_STATE_IDLE:            return "Idle";
        case GATE_STATE_WAITING_BACKEND: return "Waiting_backend";
        case GATE_STATE_OPEN:            return "Open";
        case GATE_STATE_CLEAR_WAIT:      return "Clear_wait";
        case GATE_STATE_CLOSING:         return "Closing";
        case GATE_STATE_REVIEW_REQUIRED: return "Review_required";
        default:                         return "Unknown";
    }
}

static void openGateServo(GateIndex gate) {
    if (gate == GATE_IDX_IN) {
        openEntryBarrier();
    } else {
        openExitBarrier();
    }
}

static void closeGateServo(GateIndex gate) {
    if (gate == GATE_IDX_IN) {
        closeEntryBarrier();
    } else {
        closeExitBarrier();
    }
}

static void refreshDisplay() {
    updateOledDashboard(
        gateStateToString(gates[GATE_IDX_IN].state),
        gateStateToString(gates[GATE_IDX_OUT].state),
        gates[GATE_IDX_IN].assignedSlotId,
        -1
    );
}

void initGateStateMachine() {
    gates[GATE_IDX_IN].gateIndex = GATE_IDX_IN;
    gates[GATE_IDX_IN].gateId = "IN";
    gates[GATE_IDX_IN].state = GATE_STATE_IDLE;
    gates[GATE_IDX_IN].currentEventId[0] = '\0';
    gates[GATE_IDX_IN].lastCommandId[0] = '\0';
    strncpy(gates[GATE_IDX_IN].assignedSlotId, "--", sizeof(gates[GATE_IDX_IN].assignedSlotId));
    gates[GATE_IDX_IN].stateEnteredMs = millis();
    gates[GATE_IDX_IN].clearStartedMs = 0;
    gates[GATE_IDX_IN].passageReported = false;

    gates[GATE_IDX_OUT].gateIndex = GATE_IDX_OUT;
    gates[GATE_IDX_OUT].gateId = "OUT";
    gates[GATE_IDX_OUT].state = GATE_STATE_IDLE;
    gates[GATE_IDX_OUT].currentEventId[0] = '\0';
    gates[GATE_IDX_OUT].lastCommandId[0] = '\0';
    strncpy(gates[GATE_IDX_OUT].assignedSlotId, "--", sizeof(gates[GATE_IDX_OUT].assignedSlotId));
    gates[GATE_IDX_OUT].stateEnteredMs = millis();
    gates[GATE_IDX_OUT].clearStartedMs = 0;
    gates[GATE_IDX_OUT].passageReported = false;

    refreshDisplay();
}

const GateContext& getGateContext(GateIndex gate) {
    return gates[gate];
}

static void updateSingleGate(GateContext& g, unsigned long nowMs) {
    bool irDetected = isGateIrStableDetected(g.gateIndex);

    switch (g.state) {
        case GATE_STATE_IDLE: {
            // Mục IV.9: Idle + stable IR detected -> create event_id; send trigger; state = Waiting_backend
            if (irDetected) {
                generateEventId(g.gateId, g.currentEventId, sizeof(g.currentEventId));
                g.passageReported = false;
                strncpy(g.assignedSlotId, "--", sizeof(g.assignedSlotId));
                g.state = GATE_STATE_WAITING_BACKEND;
                g.stateEnteredMs = nowMs;
                triggerBuzzer(60);
                publishGateDetectedEvent(g.gateId, g.currentEventId, "DETECTED", true);
                refreshDisplay();
            }
            break;
        }

        case GATE_STATE_WAITING_BACKEND: {
            // Nếu xe rời khỏi cảm biến trước khi backend ra quyết định mở cổng
            if (!irDetected && (nowMs - g.stateEnteredMs) > 1500UL) {
                publishGateDetectedEvent(g.gateId, g.currentEventId, "VEHICLE_LEFT_BEFORE_DECISION", false);
                g.currentEventId[0] = '\0';
                g.state = GATE_STATE_IDLE;
                g.stateEnteredMs = nowMs;
                refreshDisplay();
            } else if ((nowMs - g.stateEnteredMs) >= GATE_WAIT_BACKEND_TIMEOUT_MS) {
                // Quá thời gian chờ backend/AI -> chuyển Review_required, không tự mở cổng
                g.state = GATE_STATE_REVIEW_REQUIRED;
                g.stateEnteredMs = nowMs;
                triggerBuzzerPattern(2, 120, 100);
                publishGateDetectedEvent(g.gateId, g.currentEventId, "BACKEND_DECISION_TIMEOUT", irDetected);
                refreshDisplay();
            }
            break;
        }

        case GATE_STATE_OPEN: {
            // Mục IV.9: Open + stable IR clear -> start continuous-clear timer; state = Clear_wait
            if (!irDetected) {
                g.state = GATE_STATE_CLEAR_WAIT;
                g.clearStartedMs = nowMs;
                g.stateEnteredMs = nowMs;
                refreshDisplay();
            }
            break;
        }

        case GATE_STATE_CLEAR_WAIT: {
            // Mục IV.9: Clear_wait + IR detected again -> cancel timer; keep open; state = Open (T11)
            if (irDetected) {
                g.state = GATE_STATE_OPEN;
                g.clearStartedMs = 0;
                g.stateEnteredMs = nowMs;
                refreshDisplay();
            } else if ((nowMs - g.clearStartedMs) >= GATE_CLEAR_DELAY_MS) {
                // Clear_wait + clear for configured 3 seconds -> emit passage event once; issue close; state = Closing (T12)
                if (!g.passageReported) {
                    publishGatePassageConfirmed(g.gateId, g.currentEventId);
                    g.passageReported = true;
                }
                closeGateServo(g.gateIndex);
                g.state = GATE_STATE_CLOSING;
                g.stateEnteredMs = nowMs;
                triggerBuzzer(80);
                refreshDisplay();
            }
            break;
        }

        case GATE_STATE_CLOSING: {
            // Nếu trong lúc đang hạ barie mà IR phát hiện vật trở lại -> mở lại để an toàn và báo kiểm tra
            if (irDetected) {
                openGateServo(g.gateIndex);
                g.state = GATE_STATE_OPEN;
                g.stateEnteredMs = nowMs;
                publishGateDetectedEvent(g.gateId, g.currentEventId, "OBSTACLE_DURING_CLOSING", true);
                refreshDisplay();
            } else if ((nowMs - g.stateEnteredMs) >= 600UL) {
                // Hoàn tất chu trình đóng cổng
                g.currentEventId[0] = '\0';
                g.state = GATE_STATE_IDLE;
                g.stateEnteredMs = nowMs;
                refreshDisplay();
            }
            break;
        }

        case GATE_STATE_REVIEW_REQUIRED: {
            // Nếu xe đã lùi ra khỏi cổng và cổng chưa từng mở
            if (!irDetected && (nowMs - g.stateEnteredMs) > 3000UL) {
                publishGateDetectedEvent(g.gateId, g.currentEventId, "VEHICLE_LEFT_BEFORE_DECISION", false);
                g.currentEventId[0] = '\0';
                g.state = GATE_STATE_IDLE;
                g.stateEnteredMs = nowMs;
                refreshDisplay();
            }
            break;
        }
    }
}

void updateGateStateMachine() {
#if (BOARD_ROLE == BOARD_ROLE_PLATE_CTRL)
    unsigned long nowMs = millis();
    for (int i = 0; i < GATE_COUNT; ++i) {
        updateSingleGate(gates[i], nowMs);
    }
#endif
}

bool applyBackendGateCommand(
    const char* gateId,
    const char* commandId,
    const char* eventId,
    const char* action,
    const char* assignedSlotId,
    long expiresInMs,
    String& outReason
) {
#if (BOARD_ROLE != BOARD_ROLE_PLATE_CTRL)
    outReason = "WRONG_BOARD_ROLE";
    return false;
#else
    if (!gateId || !commandId || !eventId || !action || !commandId[0] || !eventId[0]) {
        outReason = "MISSING_COMMAND_FIELDS";
        return false;
    }

    GateIndex idx = (strcmp(gateId, "IN") == 0) ? GATE_IDX_IN :
                    (strcmp(gateId, "OUT") == 0) ? GATE_IDX_OUT : GATE_COUNT;
    if (idx == GATE_COUNT) {
        outReason = "INVALID_GATE_ID";
        return false;
    }

    GateContext& g = gates[idx];

    // 1. Chống lặp lệnh theo command_id (Mục IV.9 & IV.10: không nâng servo lại thành lượt mới do MQTT phát lại)
    if (g.lastCommandId[0] != '\0' && strcmp(g.lastCommandId, commandId) == 0) {
        outReason = "DUPLICATE_COMMAND_ID_ACKED";
        return true; // Vẫn trả ACK idempotent nhưng không kích servo lại
    }

    // 2. Kiểm tra hạn lệnh (expiresInMs <= 0 nghĩa là lệnh đã hết hạn)
    if (expiresInMs <= 0) {
        outReason = "COMMAND_EXPIRED";
        return false;
    }

    // 3. Kiểm tra khớp event_id của lượt đang chờ tại cổng
    if (g.currentEventId[0] == '\0' || strcmp(g.currentEventId, eventId) != 0) {
        outReason = "EVENT_ID_MISMATCH";
        return false;
    }

    if (strcmp(action, "OPEN") == 0 || strcmp(action, "APPROVE") == 0) {
        if (g.state != GATE_STATE_WAITING_BACKEND && g.state != GATE_STATE_REVIEW_REQUIRED) {
            outReason = "GATE_NOT_WAITING_PERMISSION";
            return false;
        }
        // Kiểm tra xe còn hiện diện trước khi mở (Mục IV.9)
        if (!isGateIrStableDetected(idx)) {
            outReason = "VEHICLE_NOT_PRESENT_AT_GATE";
            return false;
        }

        strncpy(g.lastCommandId, commandId, sizeof(g.lastCommandId) - 1);
        g.lastCommandId[sizeof(g.lastCommandId) - 1] = '\0';

        if (assignedSlotId && assignedSlotId[0] != '\0') {
            strncpy(g.assignedSlotId, assignedSlotId, sizeof(g.assignedSlotId) - 1);
            g.assignedSlotId[sizeof(g.assignedSlotId) - 1] = '\0';
        }

        openGateServo(idx);
        g.state = GATE_STATE_OPEN;
        g.stateEnteredMs = millis();
        triggerBuzzer(120);
        refreshDisplay();

        outReason = "SERVO_OPEN_ISSUED";
        return true;
    } else if (strcmp(action, "DENY") == 0 || strcmp(action, "REVIEW_REQUIRED") == 0) {
        if (g.state == GATE_STATE_OPEN || g.state == GATE_STATE_CLEAR_WAIT || g.state == GATE_STATE_CLOSING) {
            outReason = "GATE_ALREADY_OPEN_KEEP_LOCAL_SAFETY";
            return false;
        }
        strncpy(g.lastCommandId, commandId, sizeof(g.lastCommandId) - 1);
        g.lastCommandId[sizeof(g.lastCommandId) - 1] = '\0';
        g.state = GATE_STATE_REVIEW_REQUIRED;
        g.stateEnteredMs = millis();
        triggerBuzzerPattern(3, 100, 80);
        refreshDisplay();
        outReason = "GATE_HELD_FOR_REVIEW_OR_DENIED";
        return true;
    }

    outReason = "UNSUPPORTED_ACTION";
    return false;
#endif
}

bool simulateWokwiSerialApprove(GateIndex gate, String& outReason) {
    if (gate < 0 || gate >= GATE_COUNT) {
        outReason = "INVALID_GATE";
        return false;
    }
    GateContext& g = gates[gate];

    // Mục IV.2 & VIII.3: Chỉ chấp nhận lệnh giả lập 'i'/'o' khi IR thấy xe và cổng đang đóng/chờ
    if (!isGateIrStableDetected(gate)) {
        outReason = "IR_NO_VEHICLE_PRESENT";
        return false;
    }
    if (g.state != GATE_STATE_WAITING_BACKEND && g.state != GATE_STATE_REVIEW_REQUIRED) {
        outReason = "GATE_NOT_WAITING";
        return false;
    }

    char simCmdId[40];
    snprintf(simCmdId, sizeof(simCmdId), "wokwi-sim-%lu", (unsigned long)millis());
    return applyBackendGateCommand(
        g.gateId,
        simCmdId,
        g.currentEventId,
        "OPEN",
        (gate == GATE_IDX_IN) ? "A1" : g.assignedSlotId,
        10000L,
        outReason
    );
}
