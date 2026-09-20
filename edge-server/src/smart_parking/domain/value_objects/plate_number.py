"""Plate Number Value Object."""
from dataclasses import dataclass
import re

@dataclass(frozen=True)
class PlateNumber:
    raw_value: str

    def normalized(self) -> str:
        return re.sub(r"[^A-Z0-9]", "", self.raw_value.upper())