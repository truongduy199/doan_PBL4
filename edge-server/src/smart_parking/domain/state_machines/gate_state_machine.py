"""Gate State Machine."""
from smart_parking.domain.enums import GateStatus

class GateStateMachine:
    def __init__(self, initial_state: GateStatus = GateStatus.IDLE):
        self.state = initial_state

    def trigger_vehicle_detected(self):
        if self.state == GateStatus.IDLE:
            self.state = GateStatus.WAITING_VEHICLE

    def trigger_barrier_opened(self):
        if self.state == GateStatus.WAITING_VEHICLE:
            self.state = GateStatus.BARRIER_OPEN

    def trigger_passage_completed(self):
        if self.state == GateStatus.BARRIER_OPEN:
            self.state = GateStatus.CLOSING
            self.state = GateStatus.IDLE