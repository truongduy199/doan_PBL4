"""AI Port Interface."""
from abc import ABC, abstractmethod
from typing import Any, Tuple, Optional

class AIPort(ABC):
    @abstractmethod
    def detect_and_ocr_plate(self, frame: Any) -> Optional[str]:
        pass

    @abstractmethod
    def extract_face_embedding(self, frame: Any) -> Optional[bytes]:
        pass

    @abstractmethod
    def verify_face(self, embedding_in: bytes, embedding_out: bytes) -> Tuple[bool, float]:
        pass