"""Parking State Machine."""
from smart_parking.domain.enums import SlotStatus

class ParkingStateMachine:
    def __init__(self, initial_status: SlotStatus = SlotStatus.FREE):
        self.status = initial_status