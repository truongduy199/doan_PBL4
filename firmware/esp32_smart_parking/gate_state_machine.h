#ifndef GATE_STATE_MACHINE_H
#define GATE_STATE_MACHINE_H

enum GateState {
    GATE_IDLE,
    GATE_WAITING_VERIFY,
    GATE_OPEN,
    GATE_WAITING_PASSAGE,
    GATE_CLOSING
};

void updateGateStateMachine();

#endif // GATE_STATE_MACHINE_H