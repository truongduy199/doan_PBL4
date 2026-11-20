"""Script Seed & Công cụ Import mẫu tài xế cho Smart Parking PBL4 (Idempotent)."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np

# Ensure src/ is on sys.path when invoked directly from CLI
_EDGE_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = _EDGE_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from smart_parking.ai.face.template import FaceTemplateNormalizer
from smart_parking.ai.plate.normalizer import PlateNormalizer
from smart_parking.config.constants import (
    DEFAULT_FACE_CONFIG_VERSION,
    DEFAULT_FACE_DIMENSION,
    DEFAULT_FACE_DTYPE,
    DEFAULT_FACE_MODEL_ID,
    DEFAULT_FACE_MODEL_VERSION,
)
from smart_parking.config.settings import Settings, get_settings
from smart_parking.domain.enums import LivenessStatus, LogEventType
from smart_parking.infrastructure.database.mysql_db import MySQLDatabase, utc_now
from smart_parking.infrastructure.database.unit_of_work import UnitOfWork
from smart_parking.infrastructure.security.auth_security import hash_password
from smart_parking.infrastructure.security.embedding_cipher import EmbeddingCipher


def make_deterministic_l2_vector(seed: int, dim: int = DEFAULT_FACE_DIMENSION) -> np.ndarray:
    """Create a deterministic L2-normalized 512-D float32 vector for demo/test fixtures."""
    rng = np.random.default_rng(seed)
    raw = rng.standard_normal(dim).astype(np.float32)
    normed = FaceTemplateNormalizer.l2_normalize(raw).astype(np.float32)
    return normed


def load_embedding_from_nam_artifact(
    embedding_file: Optional[str | Path] = None,
    image_file: Optional[str | Path] = None,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Load 512-D float32 L2-normalized vector + metadata from Nam's extraction tool output
    (.json or .npy) or extract directly from an image file if InsightFace pipeline is loaded.
    Truthfully preserves liveness_status='Not_used' and liveness_score=None for offline imports.
    """
    meta: Dict[str, Any] = {
        "model_id": DEFAULT_FACE_MODEL_ID,
        "model_version": DEFAULT_FACE_MODEL_VERSION,
        "config_version": DEFAULT_FACE_CONFIG_VERSION,
        "quality_score": None,
        "liveness_status": LivenessStatus.NOT_USED.value,
        "liveness_score": None,
    }

    if embedding_file is not None:
        path = Path(embedding_file)
        if not path.is_file():
            raise FileNotFoundError(f"Không tìm thấy file embedding: {path}")
        if path.suffix.lower() == ".npy":
            vec = np.load(str(path)).astype(np.float32).reshape(-1)
            vec = FaceTemplateNormalizer.l2_normalize(vec).astype(np.float32)
            return vec, meta

        # JSON output from Nam's Buffalo-L extractor
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            vec = np.asarray(payload, dtype=np.float32).reshape(-1)
        elif isinstance(payload, dict):
            raw_vec = payload.get("embedding") or payload.get("vector")
            if raw_vec is None:
                raise ValueError("File JSON embedding thiếu trường 'embedding' hoặc 'vector'.")
            vec = np.asarray(raw_vec, dtype=np.float32).reshape(-1)
            meta["model_id"] = str(payload.get("model_id", meta["model_id"]))
            meta["model_version"] = str(payload.get("model_version", meta["model_version"]))
            meta["config_version"] = str(payload.get("config_version", meta["config_version"]))
            if payload.get("quality_score") is not None:
                meta["quality_score"] = float(payload["quality_score"])
            # Offline tool import without live camera anti-spoof MUST record 'Not_used'
            raw_liveness = payload.get("liveness_status", LivenessStatus.NOT_USED.value)
            if raw_liveness not in (
                LivenessStatus.PASSED.value,
                LivenessStatus.FAILED.value,
                LivenessStatus.ERROR.value,
                LivenessStatus.UNAVAILABLE.value,
                LivenessStatus.NOT_USED.value,
            ):
                raw_liveness = LivenessStatus.NOT_USED.value
            meta["liveness_status"] = raw_liveness
            if raw_liveness == LivenessStatus.NOT_USED.value:
                meta["liveness_score"] = None
            elif payload.get("liveness_score") is not None:
                meta["liveness_score"] = float(payload["liveness_score"])
        else:
            raise ValueError("Định dạng file JSON embedding không hợp lệ.")

        vec = FaceTemplateNormalizer.l2_normalize(vec).astype(np.float32)
        return vec, meta

    if image_file is not None:
        img_path = Path(image_file)
        if not img_path.is_file():
            raise FileNotFoundError(f"Không tìm thấy file ảnh mẫu khuôn mặt: {img_path}")
        import cv2
        from smart_parking.ai.face.insightface_adapter import InsightFaceAdapter

        img = cv2.imread(str(img_path))
        if img is None:
            raise ValueError(f"Không thể đọc ảnh từ đường dẫn: {img_path}")
        adapter = InsightFaceAdapter()
        if hasattr(adapter, "extract_embedding"):
            raw_vec = np.asarray(adapter.extract_embedding(img), dtype=np.float32).reshape(-1)
        else:
            raise RuntimeError(
                "InsightFaceAdapter chưa gắn hàm extract_embedding; hãy truyền --embedding-file (.json/.npy) từ công cụ của Nam."
            )
        vec = FaceTemplateNormalizer.l2_normalize(raw_vec).astype(np.float32)
        # Offline image import did not run live anti-spoof scan -> liveness_status='Not_used'
        meta["liveness_status"] = LivenessStatus.NOT_USED.value
        meta["liveness_score"] = None
        return vec, meta

    # Default deterministic 512-D L2-normalized vector for demo account
    return make_deterministic_l2_vector(seed=20261118), meta


def seed_demo_data(
    uow: UnitOfWork,
    cipher: EmbeddingCipher,
    settings: Optional[Settings] = None,
    plate_override: Optional[str] = None,
    embedding_file: Optional[str | Path] = None,
    image_file: Optional[str | Path] = None,
    with_test_fixtures: bool = False,
    init_slots_free: bool = False,
    now_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Idempotently seed:
    - 4 fixed parking slots: A1 (IR_A1), A2 (IR_A2), B1 (IR_B1), B2 (IR_B2)
    - 1 ADMIN account
    - 1 USER demo account + 1 normalized vehicle + 1 encrypted 512-D face template
    - Optional test fixtures (--with-test-fixtures) for automated acceptance tests (T01-T20)
    """
    cfg = settings or get_settings()
    now_dt = now_utc or utc_now()
    demo_plate = PlateNormalizer.normalize(plate_override or cfg.demo_vehicle_plate)
    vec_np, face_meta = load_embedding_from_nam_artifact(
        embedding_file=embedding_file,
        image_file=image_file,
    )
    encrypted_blob, enc_metadata = cipher.encrypt_embedding(
        vec_np,
        key_version=cfg.embedding_key_version,
    )

    admin_pw_hash = hash_password(cfg.demo_admin_password)
    user_pw_hash = hash_password(cfg.demo_user_password)

    def _tx_seed(tx) -> Dict[str, Any]:
        # 1. Seed 4 fixed slots (A1, A2, B1, B2)
        initial_slot_status = "Free" if init_slots_free else "Unknown"
        initial_seen_at = now_dt if init_slots_free else None
        slots = tx.slots.seed_default_slots(
            initial_physical_status=initial_slot_status,
            last_seen_at=initial_seen_at,
            now_utc=now_dt,
        )
        if init_slots_free:
            for idx, s in enumerate(slots, start=1):
                tx.slots.update_ir_sensor(
                    slot_id=s.slot_id,
                    physical_status="Free",
                    boot_id="BOOT-SEED-DEMO",
                    sequence=idx,
                    seen_at=now_dt,
                )

        # 2. Seed ADMIN account
        admin_user = tx.users.create_or_update(
            username=cfg.demo_admin_username,
            password_hash=admin_pw_hash,
            role="admin",
            display_name="Quản trị viên Hệ thống (ADMIN)",
            status="Active",
            now_utc=now_dt,
        )

        # 3. Seed USER demo account
        demo_user = tx.users.create_or_update(
            username=cfg.demo_user_username,
            password_hash=user_pw_hash,
            role="user",
            display_name=cfg.demo_user_display_name,
            status="Active",
            now_utc=now_dt,
        )

        # 4. Seed 1 registered vehicle for USER demo
        demo_vehicle = tx.vehicles.create_or_update(
            user_id=demo_user.user_id,
            plate_number=demo_plate,
            status="Active",
            now_utc=now_dt,
        )

        # 5. Upsert encrypted face template for USER demo (replaces old Active template atomically)
        demo_template = tx.face_templates.upsert_active_user_template(
            user_id=demo_user.user_id,
            embedding_blob=encrypted_blob,
            key_version=cfg.embedding_key_version,
            encryption_metadata=enc_metadata,
            model_id=face_meta["model_id"],
            model_version=face_meta["model_version"],
            config_version=face_meta["config_version"],
            liveness_status=face_meta["liveness_status"],
            liveness_score=face_meta["liveness_score"],
            quality_score=face_meta["quality_score"],
            embedding_size=DEFAULT_FACE_DIMENSION,
            embedding_dtype=DEFAULT_FACE_DTYPE,
            now_utc=now_dt,
        )

        tx.parking_logs.append(
            event_type=LogEventType.FACE_TEMPLATE_UPDATED.value,
            reason_code="SEED_DEMO_TEMPLATE",
            actor_user_id=admin_user.user_id,
            details={
                "target_user_id": demo_user.user_id,
                "template_id": demo_template.template_id,
                "model_id": demo_template.model_id,
                "liveness_status": demo_template.liveness_status.value,
            },
            created_at=now_dt,
        )

        fixtures_summary = []
        if with_test_fixtures:
            fixture_specs = [
                ("test_user_1", "Test@123", "Tài khoản Kiểm thử 1", "43A88881", 1001),
                ("test_user_2", "Test@123", "Tài khoản Kiểm thử 2", "43A88882", 1002),
            ]
            for uname, upass, dname, plate, seed_num in fixture_specs:
                f_user = tx.users.create_or_update(
                    username=uname,
                    password_hash=hash_password(upass),
                    role="user",
                    display_name=dname,
                    status="Active",
                    now_utc=now_dt,
                )
                f_veh = tx.vehicles.create_or_update(
                    user_id=f_user.user_id,
                    plate_number=plate,
                    status="Active",
                    now_utc=now_dt,
                )
                f_vec = make_deterministic_l2_vector(seed=seed_num)
                f_blob, f_meta = cipher.encrypt_embedding(f_vec, key_version=cfg.embedding_key_version)
                f_tpl = tx.face_templates.upsert_active_user_template(
                    user_id=f_user.user_id,
                    embedding_blob=f_blob,
                    key_version=cfg.embedding_key_version,
                    encryption_metadata=f_meta,
                    model_id=DEFAULT_FACE_MODEL_ID,
                    model_version=DEFAULT_FACE_MODEL_VERSION,
                    config_version=DEFAULT_FACE_CONFIG_VERSION,
                    liveness_status=LivenessStatus.NOT_USED.value,
                    liveness_score=None,
                    quality_score=None,
                    now_utc=now_dt,
                )
                fixtures_summary.append({
                    "user_id": f_user.user_id,
                    "username": f_user.username,
                    "vehicle_id": f_veh.vehicle_id,
                    "plate_number": f_veh.plate_number,
                    "template_id": f_tpl.template_id,
                })

        return {
            "admin": {
                "user_id": admin_user.user_id,
                "username": admin_user.username,
                "role": admin_user.role.value,
            },
            "demo_user": {
                "user_id": demo_user.user_id,
                "username": demo_user.username,
                "display_name": demo_user.display_name,
                "vehicle_id": demo_vehicle.vehicle_id,
                "plate_number": demo_vehicle.plate_number,
                "template_id": demo_template.template_id,
                "liveness_status": demo_template.liveness_status.value,
            },
            "slots_count": len(slots),
            "test_fixtures": fixtures_summary,
        }

    return uow.run_transactional(_tx_seed)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed dữ liệu demo (ADMIN, USER demo, 1 xe, 1 mẫu khuôn mặt mã hóa, 4 ô đỗ A1-B2)"
    )
    parser.add_argument(
        "--plate",
        type=str,
        default=None,
        help="Biển số xe demo gắn trên mô hình (mặc định từ DEMO_VEHICLE_PLATE, ví dụ: 43A12345)",
    )
    parser.add_argument(
        "--embedding-file",
        type=str,
        default=None,
        help="Đường dẫn file .json hoặc .npy chứa vector 512-D chuẩn hóa L2 từ công cụ Buffalo-L của Nam",
    )
    parser.add_argument(
        "--image-file",
        type=str,
        default=None,
        help="Đường dẫn ảnh mẫu tài xế để trích xuất vector 512-D nội bộ",
    )
    parser.add_argument(
        "--with-test-fixtures",
        action="store_true",
        help="Tạo thêm các tài khoản/xe test (test_user_1, test_user_2) phục vụ kiểm thử T01-T20",
    )
    parser.add_argument(
        "--init-slots-free",
        action="store_true",
        help="Đặt trạng thái vật lý ban đầu của 4 ô đỗ là Free kèm last_seen_at mới (dùng khi test web chưa nối ESP32)",
    )
    args = parser.parse_args()

    settings = get_settings()
    db = MySQLDatabase(settings)
    uow = UnitOfWork(db)
    cipher = EmbeddingCipher(
        secret_key=settings.embedding_secret_key,
        default_key_version=settings.embedding_key_version,
    )
    summary = seed_demo_data(
        uow=uow,
        cipher=cipher,
        settings=settings,
        plate_override=args.plate,
        embedding_file=args.embedding_file,
        image_file=args.image_file,
        with_test_fixtures=args.with_test_fixtures,
        init_slots_free=args.init_slots_free,
    )
    print("[OK] Seed dữ liệu demo hoàn tất:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
