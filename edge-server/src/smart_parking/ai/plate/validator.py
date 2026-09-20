"""Plate Validator."""
import re

class PlateValidator:
    @staticmethod
    def is_valid_vietnamese_plate(text: str) -> bool:
        # Định dạng cơ bản: 43A12345, 92B1234, v.v.
        pattern = r"^[0-9]{2}[A-Z]{1,2}[0-9]{4,5}$"
        return bool(re.match(pattern, text))