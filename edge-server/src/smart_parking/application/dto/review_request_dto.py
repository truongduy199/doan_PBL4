"""Review Request DTO."""
from pydantic import BaseModel
from typing import Optional

class ReviewRequestDTO(BaseModel):
    request_id: str
    session_id: str
    reason_code: str
    operator_id: Optional[str] = None
    status: str = "PENDING"