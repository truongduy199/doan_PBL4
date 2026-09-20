"""Face Template Value Object."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass(frozen=True)
class FaceTemplate:
    session_id: str
    embedding: bytes
    dimension: int
    model_id: str
    config_version: str
    expires_at: datetime
    quality_score: Optional[float] = None