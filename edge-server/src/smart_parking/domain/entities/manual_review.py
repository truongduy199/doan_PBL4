"""Manual Review Entity."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class ManualReview:
    review_id: str
    session_id: str
    reason_code: str
    status: str
    created_at: datetime
    operator_id: Optional[str] = None
    note: Optional[str] = None
    resolved_at: Optional[datetime] = None