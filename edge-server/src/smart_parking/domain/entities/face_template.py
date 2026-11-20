"""User & Session Face Template Domain Entities."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional
from smart_parking.domain.enums import FaceTemplateStatus, LivenessStatus


@dataclass
class UserFaceTemplate:
    template_id: int
    user_id: int
    embedding_blob: bytes
    embedding_size: int
    embedding_dtype: str
    model_id: str
    model_version: str
    config_version: str
    quality_score: Optional[float]
    liveness_status: LivenessStatus
    liveness_score: Optional[float]
    key_version: str
    encryption_metadata: Dict[str, Any]
    status: FaceTemplateStatus
    created_at: datetime
    revoked_at: Optional[datetime] = None


@dataclass
class SessionFaceTemplate:
    template_id: int
    session_id: str
    embedding_blob: bytes
    embedding_size: int
    embedding_dtype: str
    model_id: str
    model_version: str
    config_version: str
    quality_score: Optional[float]
    liveness_status: LivenessStatus
    liveness_score: Optional[float]
    key_version: str
    encryption_metadata: Dict[str, Any]
    captured_at: datetime
    expires_at: Optional[datetime] = None
