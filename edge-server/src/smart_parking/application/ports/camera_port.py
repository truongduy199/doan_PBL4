"""Camera Port Interface."""
from abc import ABC, abstractmethod
from typing import Any

class CameraPort(ABC):
    @abstractmethod
    def capture_frame(self, camera_id: int) -> Any:
        pass