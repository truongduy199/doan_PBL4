"""Repository Port Interface."""
from abc import ABC, abstractmethod
from typing import Optional, List
from smart_parking.domain.entities.parking_session import ParkingSession
from smart_parking.domain.entities.parking_slot import ParkingSlot

class RepositoryPort(ABC):
    @abstractmethod
    def get_session(self, session_id: str) -> Optional[ParkingSession]:
        pass

    @abstractmethod
    def save_session(self, session: ParkingSession) -> None:
        pass

    @abstractmethod
    def get_available_slot(self) -> Optional[str]:
        pass

    @abstractmethod
    def update_slot_status(self, slot_id: str, status: str) -> None:
        pass