"""InsightFace Adapter with Buffalo-L & Addon Liveness (Mục I.3, I.5 & I.8 Báo cáo PBL4)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


class InsightFaceAdapter:
    """
    Wraps InsightFace FaceAnalysis (SCRFD + ArcFace ResNet50 in buffalo_l) and addon `liveness.onnx`.
    Prioritizes CUDAExecutionProvider when available and falls back cleanly to CPUExecutionProvider.
    """

    def __init__(
        self,
        model_root: str | Path = "models/insightface",
        model_pack: str = "buffalo_l",
        det_size: int = 320,
        cpu_threads: int = 2,
        provider: str = "auto",
        liveness_enabled: bool = True,
        liveness_threshold: float = 0.80,
    ) -> None:
        self.model_root = str(model_root)
        self.model_pack = model_pack
        self.det_size = det_size
        self.cpu_threads = cpu_threads
        self.provider = provider
        self.liveness_enabled = liveness_enabled
        self.liveness_threshold = liveness_threshold
        self.app: Any = None
        self.runtime_provider: str = "CPUExecutionProvider"

    def initialize(self) -> bool:
        """Initialize FaceAnalysis with detection, recognition, and optional liveness addon."""
        try:
            import onnxruntime as ort
            from insightface.app import FaceAnalysis

            available_providers = ort.get_available_providers()
            wants_cuda = self.provider in ("auto", "cuda")
            cuda_available = "CUDAExecutionProvider" in available_providers

            if wants_cuda and cuda_available and hasattr(ort, "preload_dlls"):
                ort.preload_dlls(directory="")

            session_options = ort.SessionOptions()
            session_options.intra_op_num_threads = max(1, int(self.cpu_threads))
            session_options.inter_op_num_threads = 1
            session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            requested_providers = (
                ["CUDAExecutionProvider", "CPUExecutionProvider"]
                if wants_cuda and cuda_available
                else ["CPUExecutionProvider"]
            )

            root_path = Path(self.model_root)
            if not root_path.is_absolute():
                candidate = Path(__file__).resolve().parents[4] / self.model_root
                if candidate.is_dir():
                    root_path = candidate

            addons: List[str] = []
            if self.liveness_enabled and (root_path / "addons" / "liveness.onnx").is_file():
                addons = ["liveness"]

            def _build(providers: List[str]) -> Any:
                kwargs: dict[str, Any] = {
                    "name": self.model_pack,
                    "root": str(root_path),
                    "allowed_modules": ["detection", "recognition"],
                    "providers": providers,
                    "sess_options": session_options,
                }
                if addons:
                    kwargs["addons"] = addons
                    kwargs["liveness_mode"] = "normal"
                    kwargs["liveness_threshold"] = self.liveness_threshold
                fa = FaceAnalysis(**kwargs)
                fa.prepare(ctx_id=0, det_size=(self.det_size, self.det_size))
                return fa

            try:
                self.app = _build(requested_providers)
            except Exception:
                if requested_providers == ["CPUExecutionProvider"]:
                    raise
                logger.warning("CUDA initialization failed; falling back to CPUExecutionProvider.")
                self.app = _build(["CPUExecutionProvider"])

            model_providers = [
                m.session.get_providers()
                for m in getattr(self.app, "models", {}).values()
                if hasattr(m, "session")
            ]
            uses_cuda = bool(model_providers) and all("CUDAExecutionProvider" in p for p in model_providers)
            self.runtime_provider = "CUDAExecutionProvider" if uses_cuda else "CPUExecutionProvider"
            logger.info("InsightFace FaceAnalysis initialized (%s, addons=%s).", self.runtime_provider, addons)
            return True
        except Exception as exc:
            logger.error("Failed to initialize InsightFace: %s", exc)
            self.app = None
            return False

    def detect_faces(self, frame_bgr: Any) -> List[Any]:
        """Run SCRFD detection (+ liveness + ArcFace recognition) on a BGR frame."""
        if self.app is None:
            raise RuntimeError("AI_MODEL_UNAVAILABLE")
        return list(self.app.get(frame_bgr))

    def extract_embedding(self, frame: Any) -> Optional[bytes]:
        if not self.app:
            return None
        faces = self.app.get(frame)
        if len(faces) == 1 and getattr(faces[0], "normed_embedding", None) is not None:
            return faces[0].normed_embedding.tobytes()
        return None
