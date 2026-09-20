"""Decision Result Value Object."""
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class DecisionResult:
    allowed: bool
    reason_code: str
    score: Optional[float] = None
    detail: Optional[str] = None