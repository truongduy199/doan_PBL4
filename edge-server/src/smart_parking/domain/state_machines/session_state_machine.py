"""Session State Machine."""
from smart_parking.domain.enums import SessionStatus

class SessionStateMachine:
    def __init__(self, initial_status: SessionStatus = SessionStatus.INIT):
        self.status = initial_status

    def transition_to(self, new_status: SessionStatus):
        self.status = new_status