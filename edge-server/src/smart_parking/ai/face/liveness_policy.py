"""Face Liveness Policy."""
class FaceLivenessPolicy:
    @staticmethod
    def evaluate(score: float, threshold: float = 0.5) -> bool:
        return score >= threshold