"""Plate Normalizer."""
import re

class PlateNormalizer:
    @staticmethod
    def normalize(text: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", text.upper())