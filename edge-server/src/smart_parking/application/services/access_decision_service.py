"""Access Decision Service."""
class AccessDecisionService:
    def decide_entry(self, plate: str, face_valid: bool) -> bool:
        return bool(plate and face_valid)

    def decide_exit(self, match_score: float, threshold: float) -> bool:
        return match_score >= threshold