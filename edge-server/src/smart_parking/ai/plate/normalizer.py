"""Vietnamese License Plate Normalizer & Display Formatter."""
import re


class PlateNormalizer:
    """Unified plate normalizer used across seeding, OCR, booking, and gate check-in/out."""

    @staticmethod
    def normalize(text: str) -> str:
        """Normalize plate string: uppercase, remove all spaces/hyphens/dots/non-alphanumeric characters."""
        if not text:
            return ""
        cleaned = re.sub(r"[^A-Z0-9]", "", text.upper().strip())
        if not cleaned or len(cleaned) < 5 or len(cleaned) > 12:
            raise ValueError(f"Biển số xe không hợp lệ sau khi chuẩn hóa: '{text}'")
        return cleaned

    @staticmethod
    def format_display(plate: str) -> str:
        """Format normalized plate (e.g., '43A12345') into readable display ('43A-123.45')."""
        norm = re.sub(r"[^A-Z0-9]", "", (plate or "").upper())
        m = re.match(r"^(\d{2}[A-Z]{1,2}\d?)(\d{3})(\d{2})$", norm)
        if m:
            return f"{m.group(1)}-{m.group(2)}.{m.group(3)}"
        m4 = re.match(r"^(\d{2}[A-Z]{1,2}\d?)(\d{4})$", norm)
        if m4:
            return f"{m4.group(1)}-{m4.group(2)}"
        return norm
