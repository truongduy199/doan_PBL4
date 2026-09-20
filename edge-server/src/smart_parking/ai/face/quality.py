"""Face Quality Checker."""
class FaceQualityChecker:
    @staticmethod
    def check_blur(frame) -> float:
        return 150.0

    @staticmethod
    def check_pose(angles) -> bool:
        return True