"""Serial Port Interface."""
from abc import ABC, abstractmethod
from typing import Dict, Any

class SerialPort(ABC):
    @abstractmethod
    def send_command(self, cmd_type: str, payload: Dict[str, Any]) -> bool:
        pass