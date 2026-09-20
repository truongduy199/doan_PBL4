"""InsightFace Adapter."""
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)

class InsightFaceAdapter:
    def __init__(self, model_root: str = "models/insightface", model_pack: str = "buffalo_l"):
        self.model_root = model_root
        self.model_pack = model_pack
        self.app = None

    def initialize(self):
        """Khởi tạo FaceAnalysis từ InsightFace trên CPU."""
        try:
            from insightface.app import FaceAnalysis
            self.app = FaceAnalysis(name=self.model_pack, root=self.model_root, providers=["CPUExecutionProvider"])
            self.app.prepare(ctx_id=0, det_size=(640, 640))
            logger.info("InsightFace FaceAnalysis initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize InsightFace: {e}")

    def extract_embedding(self, frame: Any) -> Optional[bytes]:
        if not self.app:
            return None
        faces = self.app.get(frame)
        if len(faces) == 1:
            return faces[0].normed_embedding.tobytes()
        return None