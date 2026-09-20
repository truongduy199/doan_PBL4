"""Recognition Result DTO."""
from pydantic import BaseModel
from typing import Optional

class FaceRecognitionResultDTO(BaseModel):
    embedding: Optional[bytes] = None
    quality_score: float = 0.0
    is_valid: bool = False
    error_code: Optional[str] = None

class PlateRecognitionResultDTO(BaseModel):
    plate_number: Optional[str] = None
    confidence: float = 0.0
    is_valid: bool = False