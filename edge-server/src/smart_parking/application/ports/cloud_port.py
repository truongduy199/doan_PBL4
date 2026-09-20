"""Cloud Port Interface."""
from abc import ABC, abstractmethod
from typing import Dict, Any

class CloudPort(ABC):
    @abstractmethod
    def sync_session(self, session_data: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def sync_slot(self, slot_data: Dict[str, Any]) -> None:
        pass