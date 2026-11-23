"""Face Processing Pipeline for Gate IN/OUT & Internal Template Creation (Section I.5, I.8 & I.9)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from smart_parking.ai.face.insightface_adapter import InsightFaceAdapter
from smart_parking.ai.face.liveness_policy import FaceLivenessPolicy
from smart_parking.ai.face.quality import FaceQualityChecker
from smart_parking.ai.face.template import FaceTemplateNormalizer
from smart_parking.config.constants import (
    DEFAULT_FACE_CONFIG_VERSION,
    DEFAULT_FACE_DIMENSION,
    DEFAULT_FACE_DTYPE,
    DEFAULT_FACE_MODEL_ID,
    DEFAULT_FACE_MODEL_VERSION,
)
from smart_parking.domain.enums import LivenessStatus


@dataclass(frozen=True)
class FacePipelineResult:
    ok: bool
    reason_code: str
    message: str
    embedding: Optional[np.ndarray]
    quality_score: Optional[float]
    liveness_status: str
    liveness_score: Optional[float]
    model_id: str = DEFAULT_FACE_MODEL_ID
    model_version: str = DEFAULT_FACE_MODEL_VERSION
    config_version: str = DEFAULT_FACE_CONFIG_VERSION
    valid_sample_count: int = 0

    def to_template_payload(self) -> Dict[str, Any]:
        """Format dictionary directly compatible with GateDataService and seed_demo_data.py."""
        return {
            "embedding": self.embedding.tolist() if self.embedding is not None else None,
            "vector_np": self.embedding,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "config_version": self.config_version,
            "quality_score": self.quality_score,
            "liveness_status": self.liveness_status,
            "liveness_score": self.liveness_score,
            "embedding_size": DEFAULT_FACE_DIMENSION,
            "embedding_dtype": DEFAULT_FACE_DTYPE,
        }


class FacePipeline:
    """
    Executes the full face processing pipeline per Section I.5 & IV.2:
    1. Optional ROI crop by gate ('IN' or 'OUT').
    2. SCRFD detection -> enforce exactly 1 face (NO_FACE, MULTIPLE_FACES).
    3. Quality check (bbox margin, min size, 5-landmark pose, blur).
    4. Fail-closed Liveness addon check for live gate captures (`require_liveness=True`),
       or `Not_used` / `None` for controlled offline template imports (`require_liveness=False`).
    5. L2 normalization and multi-frame template aggregation.
    Never writes to database or controls barrier servos.
    """

    def __init__(
        self,
        adapter: Optional[InsightFaceAdapter] = None,
        min_face_size: int = 64,
        min_blur_var: float = 0.0,
        liveness_threshold: float = 0.80,
        model_id: str = DEFAULT_FACE_MODEL_ID,
        model_version: str = DEFAULT_FACE_MODEL_VERSION,
        config_version: str = DEFAULT_FACE_CONFIG_VERSION,
    ) -> None:
        self.adapter = adapter
        self.min_face_size = min_face_size
        self.min_blur_var = min_blur_var
        self.liveness_threshold = liveness_threshold
        self.model_id = model_id
        self.model_version = model_version
        self.config_version = config_version

    @staticmethod
    def crop_roi(frame_bgr: np.ndarray, roi: Optional[Tuple[int, int, int, int]]) -> np.ndarray:
        if roi is None:
            return frame_bgr
        h, w = frame_bgr.shape[:2]
        x1, y1, x2, y2 = roi
        x1 = max(0, min(w, int(x1)))
        y1 = max(0, min(h, int(y1)))
        x2 = max(0, min(w, int(x2)))
        y2 = max(0, min(h, int(y2)))
        if x2 <= x1 or y2 <= y1:
            return frame_bgr
        return frame_bgr[y1:y2, x1:x2].copy()

    def process_frame(
        self,
        frame_bgr: np.ndarray,
        *,
        require_liveness: bool = True,
        roi: Optional[Tuple[int, int, int, int]] = None,
    ) -> FacePipelineResult:
        """Process a single BGR frame and return structured FacePipelineResult."""
        if frame_bgr is None or not isinstance(frame_bgr, np.ndarray) or frame_bgr.ndim != 3 or frame_bgr.size == 0:
            return FacePipelineResult(
                ok=False,
                reason_code="FACE_QUALITY_FAILED",
                message="Khung hình khuôn mặt rỗng hoặc không giải mã được.",
                embedding=None,
                quality_score=None,
                liveness_status=LivenessStatus.UNAVAILABLE.value if require_liveness else LivenessStatus.NOT_USED.value,
                liveness_score=None,
                model_id=self.model_id,
                model_version=self.model_version,
                config_version=self.config_version,
            )

        target_frame = self.crop_roi(frame_bgr, roi)

        if self.adapter is None or getattr(self.adapter, "app", None) is None:
            return FacePipelineResult(
                ok=False,
                reason_code="AI_MODEL_UNAVAILABLE",
                message="Model InsightFace Buffalo-L chưa được khởi tạo.",
                embedding=None,
                quality_score=None,
                liveness_status=LivenessStatus.UNAVAILABLE.value if require_liveness else LivenessStatus.NOT_USED.value,
                liveness_score=None,
                model_id=self.model_id,
                model_version=self.model_version,
                config_version=self.config_version,
            )

        try:
            faces = self.adapter.app.get(target_frame)
        except Exception as exc:
            return FacePipelineResult(
                ok=False,
                reason_code="FACE_INFERENCE_ERROR",
                message=f"Lỗi suy luận InsightFace: {exc}",
                embedding=None,
                quality_score=None,
                liveness_status=LivenessStatus.ERROR.value if require_liveness else LivenessStatus.NOT_USED.value,
                liveness_score=None,
                model_id=self.model_id,
                model_version=self.model_version,
                config_version=self.config_version,
            )

        if not faces or len(faces) == 0:
            return FacePipelineResult(
                ok=False,
                reason_code="NO_FACE",
                message="Không phát hiện khuôn mặt trong vùng nhận diện.",
                embedding=None,
                quality_score=None,
                liveness_status=LivenessStatus.UNAVAILABLE.value if require_liveness else LivenessStatus.NOT_USED.value,
                liveness_score=None,
                model_id=self.model_id,
                model_version=self.model_version,
                config_version=self.config_version,
            )

        if len(faces) > 1:
            return FacePipelineResult(
                ok=False,
                reason_code="MULTIPLE_FACES",
                message=f"Phát hiện {len(faces)} khuôn mặt trong ROI; chỉ cho phép đúng 1 người.",
                embedding=None,
                quality_score=None,
                liveness_status=LivenessStatus.UNAVAILABLE.value if require_liveness else LivenessStatus.NOT_USED.value,
                liveness_score=None,
                model_id=self.model_id,
                model_version=self.model_version,
                config_version=self.config_version,
            )

        face = faces[0]

        # 1. Fail-closed Liveness evaluation (Section I.8 & T20)
        live_res = FaceLivenessPolicy.evaluate_face_object(
            face,
            threshold=self.liveness_threshold,
            require_liveness=require_liveness,
        )
        if not live_res.is_valid_live:
            return FacePipelineResult(
                ok=False,
                reason_code=live_res.reason_code,
                message=live_res.message,
                embedding=None,
                quality_score=None,
                liveness_status=live_res.liveness_status,
                liveness_score=live_res.liveness_score,
                model_id=self.model_id,
                model_version=self.model_version,
                config_version=self.config_version,
            )

        # 2. Quality & Pose evaluation
        qual_res = FaceQualityChecker.evaluate(
            face,
            target_frame,
            min_face_size=self.min_face_size,
            min_blur_var=self.min_blur_var,
        )
        if not qual_res.passed:
            return FacePipelineResult(
                ok=False,
                reason_code=qual_res.reason_code,
                message=qual_res.message,
                embedding=None,
                quality_score=None,
                liveness_status=live_res.liveness_status,
                liveness_score=live_res.liveness_score,
                model_id=self.model_id,
                model_version=self.model_version,
                config_version=self.config_version,
            )

        # 3. Extract & normalize 512-D embedding
        raw_emb = getattr(face, "normed_embedding", None)
        if raw_emb is None:
            raw_emb = getattr(face, "embedding", None)
        if raw_emb is None:
            return FacePipelineResult(
                ok=False,
                reason_code="FACE_INFERENCE_ERROR",
                message="Model không trả về vector embedding 512-D.",
                embedding=None,
                quality_score=qual_res.quality_score,
                liveness_status=live_res.liveness_status,
                liveness_score=live_res.liveness_score,
                model_id=self.model_id,
                model_version=self.model_version,
                config_version=self.config_version,
            )

        try:
            norm_emb = FaceTemplateNormalizer.l2_normalize(np.asarray(raw_emb, dtype=np.float32))
        except ValueError as exc:
            return FacePipelineResult(
                ok=False,
                reason_code="FACE_INFERENCE_ERROR",
                message=str(exc),
                embedding=None,
                quality_score=qual_res.quality_score,
                liveness_status=live_res.liveness_status,
                liveness_score=live_res.liveness_score,
                model_id=self.model_id,
                model_version=self.model_version,
                config_version=self.config_version,
            )

        return FacePipelineResult(
            ok=True,
            reason_code="OK",
            message="Tạo template khuôn mặt hợp lệ.",
            embedding=norm_emb,
            quality_score=qual_res.quality_score,
            liveness_status=live_res.liveness_status,
            liveness_score=live_res.liveness_score,
            model_id=self.model_id,
            model_version=self.model_version,
            config_version=self.config_version,
            valid_sample_count=1,
        )

    def process_frames(
        self,
        frames_bgr: Sequence[np.ndarray],
        *,
        require_liveness: bool = True,
        min_valid_samples: int = 1,
        min_sample_similarity: float = 0.65,
        roi: Optional[Tuple[int, int, int, int]] = None,
    ) -> FacePipelineResult:
        """Aggregate multiple frames into a single L2-normalized 512-D template (Section I.5)."""
        if not frames_bgr:
            return FacePipelineResult(
                ok=False,
                reason_code="NO_FACE",
                message="Không có khung hình nào để xử lý khuôn mặt.",
                embedding=None,
                quality_score=None,
                liveness_status=LivenessStatus.UNAVAILABLE.value if require_liveness else LivenessStatus.NOT_USED.value,
                liveness_score=None,
                model_id=self.model_id,
                model_version=self.model_version,
                config_version=self.config_version,
            )

        valid_embeddings: List[np.ndarray] = []
        quality_scores: List[float] = []
        live_scores: List[float] = []
        last_failure: Optional[FacePipelineResult] = None

        for frame in frames_bgr:
            res = self.process_frame(frame, require_liveness=require_liveness, roi=roi)
            if res.ok and res.embedding is not None:
                valid_embeddings.append(res.embedding)
                if res.quality_score is not None:
                    quality_scores.append(res.quality_score)
                if res.liveness_score is not None:
                    live_scores.append(res.liveness_score)
            else:
                last_failure = res

        if len(valid_embeddings) < max(1, min_valid_samples):
            if last_failure is not None:
                return last_failure
            return FacePipelineResult(
                ok=False,
                reason_code="FACE_REVIEW_REQUIRED",
                message="Không đủ số mẫu khuôn mặt hợp lệ để tạo template.",
                embedding=None,
                quality_score=None,
                liveness_status=LivenessStatus.UNAVAILABLE.value if require_liveness else LivenessStatus.NOT_USED.value,
                liveness_score=None,
                model_id=self.model_id,
                model_version=self.model_version,
                config_version=self.config_version,
            )

        try:
            normalized_samples = [FaceTemplateNormalizer.l2_normalize(e) for e in valid_embeddings]
            for index, sample in enumerate(normalized_samples):
                if any(float(np.dot(sample, other)) < min_sample_similarity for other in normalized_samples[index + 1:]):
                    return FacePipelineResult(
                        False, "FACE_SAMPLES_INCONSISTENT", "Các ảnh khuôn mặt không đủ nhất quán để tạo một mẫu.",
                        None, None, LivenessStatus.PASSED.value if require_liveness else LivenessStatus.NOT_USED.value,
                        min(live_scores) if live_scores else None, self.model_id, self.model_version, self.config_version)
            aggregated_tpl = FaceTemplateNormalizer.build_template(normalized_samples)
        except ValueError as exc:
            return FacePipelineResult(
                ok=False,
                reason_code="FACE_REVIEW_REQUIRED",
                message=str(exc),
                embedding=None,
                quality_score=None,
                liveness_status=LivenessStatus.ERROR.value if require_liveness else LivenessStatus.NOT_USED.value,
                liveness_score=None,
                model_id=self.model_id,
                model_version=self.model_version,
                config_version=self.config_version,
            )

        avg_quality = round(float(np.mean(quality_scores)), 4) if quality_scores else None
        avg_live_score = round(float(np.mean(live_scores)), 4) if (require_liveness and live_scores) else None
        live_status = LivenessStatus.PASSED.value if require_liveness else LivenessStatus.NOT_USED.value

        return FacePipelineResult(
            ok=True,
            reason_code="OK",
            message=f"Tổng hợp template thành công từ {len(valid_embeddings)} frame.",
            embedding=aggregated_tpl,
            quality_score=avg_quality,
            liveness_status=live_status,
            liveness_score=avg_live_score,
            model_id=self.model_id,
            model_version=self.model_version,
            config_version=self.config_version,
            valid_sample_count=len(valid_embeddings),
        )

    def process(self, frame: np.ndarray) -> FacePipelineResult:
        """Backward-compatible single-frame entrypoint."""
        return self.process_frame(frame, require_liveness=True)
