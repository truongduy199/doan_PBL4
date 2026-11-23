"""Plate Validator."""
import re

class PlateValidator:
    @staticmethod
    def is_valid_vietnamese_plate(text: str) -> bool:
        # Định dạng cơ bản: 43A12345, 92B1234, v.v.
        # Include a letter+digit series, e.g. 85H6-503.46 -> 85H650346.
        pattern = r"^[0-9]{2}(?:[A-Z]{1,2}[0-9]{4,5}|[A-Z][0-9][0-9]{5})$"
        return bool(re.match(pattern, text))
