"""Chuong trinh thu nghiem xac thuc khuon mat bang webcam va InsightFace.

Quy trinh:
1. Moi khuon mat phai vuot qua model liveness truoc khi duoc tao embedding.
2. Nguoi thu nhat nhan SPACE de quet va tao face template trong RAM.
3. Doi sang nguoi thu hai, sau do nhan SPACE de quet va so sanh.
4. Chuong trinh hien thi MATCH hoac NOT MATCH cung cosine score.

Anh webcam va embedding khong duoc ghi xuong dia.
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
import time
from enum import Enum, auto
from pathlib import Path

import cv2
import numpy as np

EDGE_SERVER_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = EDGE_SERVER_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from smart_parking.ai.face.insightface_adapter import InsightFaceAdapter
from smart_parking.ai.face.template import FaceTemplateNormalizer
from smart_parking.ai.face.verifier import FaceVerifier

WINDOW_NAME = "InsightFace Webcam Verification"
LOGGER = logging.getLogger(__name__)


class Phase(Enum):
    ENROLL_READY = auto()
    ENROLL_CAPTURE = auto()
    VERIFY_READY = auto()
    VERIFY_CAPTURE = auto()
    RESULT = auto()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Quet khuon mat thu nhat va xac thuc khuon mat thu hai bang webcam."
    )
    parser.add_argument(
        "--camera", type=int, default=0, help="Chi so webcam, mac dinh: 0"
    )
    parser.add_argument(
        "--provider",
        choices=("auto", "cuda", "cpu"),
        default="auto",
        help="Backend inference: auto uu tien CUDA, mac dinh: auto",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.65,
        help="Nguong cosine de chap nhan, mac dinh: 0.65",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=5,
        help="So embedding dung de tao moi template, mac dinh: 5",
    )
    parser.add_argument(
        "--min-face-size",
        type=int,
        default=80,
        help="Kich thuoc canh khuon mat toi thieu theo pixel, mac dinh: 80",
    )
    parser.add_argument(
        "--det-size",
        type=int,
        default=320,
        help="Do phan giai detector vuong, mac dinh: 320",
    )
    parser.add_argument(
        "--cpu-threads",
        type=int,
        default=2,
        help="So CPU thread cho ONNX Runtime, mac dinh: 2",
    )
    parser.add_argument(
        "--inference-fps",
        type=float,
        default=4.0,
        help="So lan suy luan moi giay, mac dinh: 4",
    )
    parser.add_argument(
        "--ready-frames",
        type=int,
        default=3,
        help="So frame song hop le lien tiep de mo khoa SPACE, mac dinh: 3",
    )
    parser.add_argument(
        "--liveness-threshold",
        type=float,
        default=0.8,
        help="Nguong chong gia mao trong khoang [0, 1], mac dinh: 0.8",
    )
    parser.add_argument(
        "--model-root",
        type=Path,
        default=EDGE_SERVER_DIR / "models" / "insightface",
        help="Thu muc goc chua model InsightFace",
    )
    args = parser.parse_args()

    if not -1.0 <= args.threshold <= 1.0:
        parser.error("--threshold phai nam trong khoang [-1, 1]")
    if args.samples < 1:
        parser.error("--samples phai lon hon hoac bang 1")
    if args.min_face_size < 1:
        parser.error("--min-face-size phai lon hon hoac bang 1")
    if args.det_size < 128:
        parser.error("--det-size phai lon hon hoac bang 128")
    if args.cpu_threads < 1:
        parser.error("--cpu-threads phai lon hon hoac bang 1")
    if args.inference_fps <= 0:
        parser.error("--inference-fps phai lon hon 0")
    if args.ready_frames < 1:
        parser.error("--ready-frames phai lon hon hoac bang 1")
    if not 0.0 <= args.liveness_threshold <= 1.0:
        parser.error("--liveness-threshold phai nam trong khoang [0, 1]")
    return args


def open_camera(index: int) -> cv2.VideoCapture:
    """Mo webcam qua cac backend pho bien va tra ve backend dau tien hoat dong."""
    backends = [cv2.CAP_ANY]
    if sys.platform == "win32":
        backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]

    for backend in backends:
        capture = cv2.VideoCapture(index, backend)
        if capture.isOpened():
            return capture
        capture.release()

    raise RuntimeError(
        f"Khong mo duoc webcam {index}. Hay kiem tra Camera privacy settings "
        "hoac thu --camera 1."
    )


def make_template(samples: list[np.ndarray]) -> np.ndarray:
    """Lay trung binh cac embedding va chuan hoa L2."""
    if not samples:
        raise ValueError("Khong co embedding de tao template")
    mean_embedding = np.mean(np.stack(samples), axis=0)
    return FaceTemplateNormalizer.l2_normalize(mean_embedding.astype(np.float32))


def initialize_adapter(
    model_root: Path,
    det_size: int,
    cpu_threads: int,
    provider: str,
    liveness_threshold: float,
) -> InsightFaceAdapter:
    """Khoi tao detector, anti-spoof va recognition; uu tien CUDA."""
    import onnxruntime as ort
    from insightface.app import FaceAnalysis

    available_providers = ort.get_available_providers()
    wants_cuda = provider in ("auto", "cuda")
    cuda_available = "CUDAExecutionProvider" in available_providers

    if provider == "cuda" and not cuda_available:
        raise RuntimeError(
            "Da yeu cau CUDA nhung ONNX Runtime khong co CUDAExecutionProvider"
        )

    if wants_cuda and cuda_available and hasattr(ort, "preload_dlls"):
        # Nap CUDA/cuDNN tu cac NVIDIA package trong virtual environment.
        ort.preload_dlls(directory="")

    session_options = ort.SessionOptions()
    session_options.intra_op_num_threads = cpu_threads
    session_options.inter_op_num_threads = 1
    session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

    requested_providers = (
        ["CUDAExecutionProvider", "CPUExecutionProvider"]
        if wants_cuda and cuda_available
        else ["CPUExecutionProvider"]
    )

    def build_app(providers: list[str]) -> FaceAnalysis:
        app = FaceAnalysis(
            name="buffalo_l",
            root=str(model_root),
            allowed_modules=["detection", "recognition"],
            addons=["liveness"],
            liveness_mode="normal",
            liveness_threshold=liveness_threshold,
            providers=providers,
            sess_options=session_options,
        )
        app.prepare(ctx_id=0, det_size=(det_size, det_size))
        return app

    adapter = InsightFaceAdapter(model_root=str(model_root), model_pack="buffalo_l")
    try:
        adapter.app = build_app(requested_providers)
    except Exception:
        if provider != "auto" or requested_providers == ["CPUExecutionProvider"]:
            raise
        LOGGER.exception("CUDA khoi tao that bai; fallback ve CPU")
        adapter.app = build_app(["CPUExecutionProvider"])

    model_providers = [
        model.session.get_providers() for model in adapter.app.models.values()
    ]
    uses_cuda = bool(model_providers) and all(
        "CUDAExecutionProvider" in providers for providers in model_providers
    )
    adapter.runtime_provider = (
        "CUDAExecutionProvider" if uses_cuda else "CPUExecutionProvider"
    )
    return adapter


def put_lines(
    frame: np.ndarray,
    lines: list[str],
    *,
    origin_y: int = 30,
    color: tuple[int, int, int] = (255, 255, 255),
) -> None:
    """Ve cac dong ASCII de OpenCV hien thi on dinh tren moi may."""
    for index, line in enumerate(lines):
        y = origin_y + index * 30
        cv2.putText(
            frame,
            line,
            (15, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 0),
            4,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            line,
            (15, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2,
            cv2.LINE_AA,
        )


def evaluate_liveness(
    face: object,
    threshold: float,
) -> tuple[bool, float | None, str]:
    """Doc ket qua anti-spoof theo kieu fail-closed."""
    result = getattr(face, "liveness", None)
    if result is None:
        return False, None, "LOCKED - liveness result unavailable"

    status = getattr(result, "status", None)
    if status == "input_rejected":
        return False, None, "LOCKED - step back and keep face inside frame"
    if status != "ok":
        return False, None, "LOCKED - invalid liveness result"

    raw_score = getattr(result, "live_score", None)
    try:
        live_score = float(raw_score)
    except (TypeError, ValueError):
        return False, None, "LOCKED - invalid liveness score"
    if not math.isfinite(live_score) or not 0.0 <= live_score <= 1.0:
        return False, None, "LOCKED - invalid liveness score"

    is_live = getattr(result, "is_live", None)
    if is_live is not True or live_score < threshold:
        return (
            False,
            live_score,
            f"SPOOF BLOCKED - fake/phone/photo suspected ({live_score:.2f})",
        )
    return True, live_score, f"LIVE - liveness score {live_score:.2f}"


def analyze_frame(
    frame: np.ndarray,
    adapter: InsightFaceAdapter,
    min_face_size: int,
    liveness_threshold: float,
) -> tuple[list[object], np.ndarray | None, str, float | None]:
    """Chi tra embedding khi mot khuon mat that vuot qua moi kiem tra."""
    faces = adapter.app.get(frame)
    valid_embedding: np.ndarray | None = None
    live_score: float | None = None

    if len(faces) == 0:
        status = "LOCKED - no face detected"
    elif len(faces) > 1:
        status = f"LOCKED - {len(faces)} faces detected; keep only one"
    else:
        face = faces[0]
        is_live, live_score, status = evaluate_liveness(face, liveness_threshold)
        if is_live:
            is_valid, status = validate_face_position(face, frame.shape, min_face_size)
            if is_valid:
                raw_embedding = getattr(face, "normed_embedding", None)
                if raw_embedding is None:
                    status = "LOCKED - recognition blocked after liveness check"
                else:
                    valid_embedding = np.asarray(raw_embedding, dtype=np.float32).copy()
                    status = f"LIVE - liveness score {live_score:.2f}"

    return faces, valid_embedding, status, live_score


def validate_face_position(
    face: object,
    frame_shape: tuple[int, ...],
    min_face_size: int,
) -> tuple[bool, str]:
    """Kiem tra mat day du, o giua khung hinh va huong gan thang camera."""
    frame_height, frame_width = frame_shape[:2]
    x1, y1, x2, y2 = np.asarray(face.bbox, dtype=np.float32)
    face_width = float(x2 - x1)
    face_height = float(y2 - y1)
    face_size = min(face_width, face_height)

    if face_width <= 0 or face_height <= 0:
        return False, "LOCKED - invalid face box"

    # Can mot khoang trong quanh bbox de bao dam khong bi cat mat o canh camera.
    margin_x = max(10.0, face_width * 0.10)
    margin_y = max(10.0, face_height * 0.10)
    if (
        x1 < margin_x
        or y1 < margin_y
        or x2 > frame_width - margin_x
        or y2 > frame_height - margin_y
    ):
        return False, "LOCKED - incomplete face; move fully inside frame"

    if face_size < min_face_size:
        return False, f"LOCKED - move closer; face size {face_size:.0f}px"

    if face_width > frame_width * 0.62 or face_height > frame_height * 0.78:
        return False, "LOCKED - move farther from camera"

    center_x = (x1 + x2) * 0.5
    center_y = (y1 + y2) * 0.5
    if (
        abs(center_x - frame_width * 0.5) > frame_width * 0.27
        or abs(center_y - frame_height * 0.5) > frame_height * 0.27
    ):
        return False, "LOCKED - center your face in the guide"

    landmarks = getattr(face, "kps", None)
    if landmarks is None or np.asarray(landmarks).shape != (5, 2):
        return False, "LOCKED - facial landmarks are incomplete"

    left_eye, right_eye, nose, left_mouth, right_mouth = np.asarray(
        landmarks, dtype=np.float32
    )
    eye_vector = right_eye - left_eye
    eye_distance = float(np.linalg.norm(eye_vector))
    if eye_distance < 1.0:
        return False, "LOCKED - eyes are not clear"

    roll_degrees = abs(
        math.degrees(math.atan2(float(eye_vector[1]), float(eye_vector[0])))
    )
    if roll_degrees > 12.0:
        return False, "LOCKED - keep your head upright"

    left_nose_distance = float(np.linalg.norm(nose - left_eye))
    right_nose_distance = float(np.linalg.norm(nose - right_eye))
    yaw_asymmetry = abs(left_nose_distance - right_nose_distance) / max(
        left_nose_distance, right_nose_distance, 1.0
    )
    eye_midpoint = (left_eye + right_eye) * 0.5
    nose_horizontal_offset = abs(float(nose[0] - eye_midpoint[0])) / eye_distance
    if yaw_asymmetry > 0.28 or nose_horizontal_offset > 0.25:
        return False, "LOCKED - look straight at the camera"

    eye_line_y = float((left_eye[1] + right_eye[1]) * 0.5)
    mouth_line_y = float((left_mouth[1] + right_mouth[1]) * 0.5)
    eye_to_mouth = mouth_line_y - eye_line_y
    if eye_to_mouth <= 1.0:
        return False, "LOCKED - facial landmarks are invalid"
    nose_vertical_ratio = float(nose[1] - eye_line_y) / eye_to_mouth
    if not 0.25 <= nose_vertical_ratio <= 0.90:
        return False, "LOCKED - keep your face level with the camera"

    return True, "Face position valid"


def draw_face_boxes(
    frame: np.ndarray,
    faces: list[object],
    valid_embedding: np.ndarray | None,
    capture_ready: bool,
) -> None:
    """Ve ket qua inference gan nhat len preview webcam."""
    for face in faces:
        x1, y1, x2, y2 = face.bbox.astype(int)
        if len(faces) > 1 or valid_embedding is None:
            box_color = (0, 0, 255)
        elif not capture_ready:
            box_color = (0, 255, 255)
        else:
            box_color = (0, 255, 0)
        cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)


def draw_alignment_guide(frame: np.ndarray) -> None:
    """Ve vung trung tam de nguoi dung can chinh khuon mat."""
    height, width = frame.shape[:2]
    center = (width // 2, height // 2)
    axes = (int(width * 0.22), int(height * 0.38))
    cv2.ellipse(frame, center, axes, 0, 0, 360, (180, 180, 180), 1, cv2.LINE_AA)


def reset_session() -> (
    tuple[Phase, list[np.ndarray], list[np.ndarray], np.ndarray | None]
):
    print(
        "\n[1/2] Nguoi thu nhat: nhin thang vao webcam va nhan SPACE de bat dau quet."
    )
    return Phase.ENROLL_READY, [], [], None


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    cv2.setNumThreads(1)

    model_root = args.model_root.expanduser().resolve()
    if not (model_root / "models" / "buffalo_l").is_dir():
        print(f"Khong tim thay model buffalo_l trong: {model_root}", file=sys.stderr)
        return 2
    liveness_model = model_root / "addons" / "liveness.onnx"
    if not liveness_model.is_file():
        print(
            f"Khong tim thay model anti-spoof: {liveness_model}\n"
            "Chay lenh ensure_addon trong HUONG_DAN_SETUP_THANH_VIEN.md.",
            file=sys.stderr,
        )
        return 2

    print(
        "Dang khoi tao InsightFace "
        f"(provider={args.provider}, CPU fallback={args.cpu_threads} threads, "
        f"detector {args.det_size}x{args.det_size}, "
        f"{args.inference_fps:g} inference FPS)..."
    )
    print(
        "Anti-spoof bat buoc: "
        f"threshold={args.liveness_threshold:.2f}, "
        f"can {args.ready_frames} frame song lien tiep."
    )
    try:
        adapter = initialize_adapter(
            model_root,
            args.det_size,
            args.cpu_threads,
            args.provider,
            args.liveness_threshold,
        )
    except Exception:
        LOGGER.exception("Khoi tao InsightFace that bai")
        print("Khoi tao InsightFace that bai. Xem log phia tren.", file=sys.stderr)
        return 2

    runtime_provider = adapter.runtime_provider
    print(f"Inference provider dang dung: {runtime_provider}")

    try:
        camera = open_camera(args.camera)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 3

    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    verifier = FaceVerifier(t_accept=args.threshold, t_reject=args.threshold)
    phase, enroll_samples, verify_samples, enrolled_template = reset_session()
    result_text = ""
    result_color = (255, 255, 255)
    result_score = 0.0
    inference_interval = 1.0 / args.inference_fps
    last_inference_at = 0.0
    faces: list[object] = []
    embedding: np.ndarray | None = None
    liveness_score: float | None = None
    face_status = "Waiting for face analysis..."
    valid_streak = 0
    capture_ready = False

    try:
        while True:
            ok, frame = camera.read()
            if not ok or frame is None:
                print("Khong doc duoc frame tu webcam.", file=sys.stderr)
                return 4

            frame = cv2.flip(frame, 1)
            clean_frame = frame.copy()
            now = time.perf_counter()
            did_inference = False
            if phase != Phase.RESULT and now - last_inference_at >= inference_interval:
                faces, embedding, face_status, liveness_score = analyze_frame(
                    clean_frame,
                    adapter,
                    args.min_face_size,
                    args.liveness_threshold,
                )
                last_inference_at = time.perf_counter()
                did_inference = True

            if did_inference:
                valid_streak = valid_streak + 1 if embedding is not None else 0

            capture_ready = embedding is not None and (
                phase in (Phase.ENROLL_CAPTURE, Phase.VERIFY_CAPTURE)
                or valid_streak >= args.ready_frames
            )
            if embedding is not None:
                if phase in (Phase.ENROLL_READY, Phase.VERIFY_READY):
                    if capture_ready:
                        face_status = "READY - SPACE unlocked"
                    else:
                        face_status = (
                            f"Hold still and look straight "
                            f"({valid_streak}/{args.ready_frames})"
                        )
                elif phase in (Phase.ENROLL_CAPTURE, Phase.VERIFY_CAPTURE):
                    face_status = "SCANNING - keep this position"

            if (
                phase == Phase.ENROLL_CAPTURE
                and did_inference
                and embedding is not None
            ):
                enroll_samples.append(embedding)
                if len(enroll_samples) >= args.samples:
                    enrolled_template = make_template(enroll_samples)
                    phase = Phase.VERIFY_READY
                    print(
                        f"Da luu template cua nguoi thu nhat tu {args.samples} mau trong RAM."
                    )
                    print(
                        "[2/2] Moi nguoi thu hai vao khung hinh, sau do nhan SPACE de xac thuc."
                    )
                    faces = []
                    embedding = None
                    liveness_score = None
                    valid_streak = 0
                    capture_ready = False
                    face_status = "LOCKED - change to the second person"
                    last_inference_at = 0.0

            elif (
                phase == Phase.VERIFY_CAPTURE
                and did_inference
                and embedding is not None
            ):
                verify_samples.append(embedding)
                if len(verify_samples) >= args.samples:
                    assert enrolled_template is not None
                    candidate_template = make_template(verify_samples)
                    decision, result_score = verifier.verify(
                        enrolled_template, candidate_template
                    )
                    is_match = decision == "ACCEPT"
                    result_text = "MATCH" if is_match else "NOT MATCH"
                    result_color = (0, 255, 0) if is_match else (0, 0, 255)
                    phase = Phase.RESULT
                    face_status = "Verification finished - press R to restart"
                    vietnamese_result = "CHINH XAC" if is_match else "KHONG CHINH XAC"
                    print(
                        f"Ket qua: {vietnamese_result} | cosine={result_score:.4f} "
                        f"| threshold={args.threshold:.4f}"
                    )

            if phase != Phase.RESULT:
                draw_alignment_guide(frame)
                draw_face_boxes(frame, faces, embedding, capture_ready)

            if phase == Phase.ENROLL_READY:
                title = "STEP 1: FIRST PERSON"
                action = (
                    "SPACE unlocked - press to scan"
                    if capture_ready
                    else "SPACE locked - align your full face"
                )
            elif phase == Phase.ENROLL_CAPTURE:
                title = "SCANNING FIRST PERSON"
                action = f"Samples: {len(enroll_samples)}/{args.samples}"
            elif phase == Phase.VERIFY_READY:
                title = "STEP 2: SECOND PERSON"
                action = (
                    "SPACE unlocked - press to verify"
                    if capture_ready
                    else "SPACE locked - align the second face"
                )
            elif phase == Phase.VERIFY_CAPTURE:
                title = "SCANNING SECOND PERSON"
                action = f"Samples: {len(verify_samples)}/{args.samples}"
            else:
                title = result_text
                action = f"Cosine: {result_score:.4f} | Threshold: {args.threshold:.4f}"

            title_color = result_color if phase == Phase.RESULT else (255, 255, 255)
            if phase == Phase.RESULT:
                status_color = result_color
            elif capture_ready:
                status_color = (0, 255, 0)
            elif embedding is not None:
                status_color = (0, 255, 255)
            else:
                status_color = (0, 0, 255)
            put_lines(frame, [title, action], color=title_color)
            put_lines(frame, [face_status], origin_y=90, color=status_color)
            put_lines(
                frame,
                [
                    f"Provider: {runtime_provider}",
                    "Liveness: "
                    + (
                        f"{liveness_score:.2f} / {args.liveness_threshold:.2f}"
                        if liveness_score is not None
                        else "waiting"
                    ),
                ],
                origin_y=120,
                color=(220, 220, 220),
            )
            put_lines(
                frame,
                ["SPACE: capture | R: restart | Q/ESC: quit"],
                origin_y=frame.shape[0] - 20,
                color=(220, 220, 220),
            )
            cv2.imshow(WINDOW_NAME, frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("r"):
                phase, enroll_samples, verify_samples, enrolled_template = (
                    reset_session()
                )
                result_text = ""
                result_score = 0.0
                last_inference_at = 0.0
                faces = []
                embedding = None
                liveness_score = None
                face_status = "Waiting for face analysis..."
                valid_streak = 0
                capture_ready = False
                continue
            if key == 32:  # noqa: SIM102 - tach xu ly SPACE de de doc state machine
                if phase in (Phase.ENROLL_READY, Phase.VERIFY_READY):
                    # Kiem tra lai frame sach ngay luc bam phim, khong tin vao
                    # ket qua cache neu nguoi dung vua di chuyen ra khoi khung.
                    (
                        current_faces,
                        current_embedding,
                        current_status,
                        current_liveness_score,
                    ) = analyze_frame(
                        clean_frame,
                        adapter,
                        args.min_face_size,
                        args.liveness_threshold,
                    )
                    liveness_score = current_liveness_score
                    if current_embedding is None:
                        faces = current_faces
                        embedding = None
                        valid_streak = 0
                        capture_ready = False
                        face_status = current_status
                        print(f"SPACE bi khoa: {face_status}")
                    elif not capture_ready:
                        print(
                            "SPACE bi khoa: can giu tu the hop le "
                            f"{args.ready_frames} frame lien tiep"
                        )
                    elif phase == Phase.ENROLL_READY:
                        embedding = current_embedding
                        enroll_samples = []
                        phase = Phase.ENROLL_CAPTURE
                        print("Dang quet nguoi thu nhat...")
                    elif phase == Phase.VERIFY_READY:
                        embedding = current_embedding
                        verify_samples = []
                        phase = Phase.VERIFY_CAPTURE
                        print("Dang quet nguoi thu hai...")

    except KeyboardInterrupt:
        print("Da dung theo yeu cau nguoi dung.")
    finally:
        camera.release()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
