"""
CLI Script giả lập luồng cổng vào/ra & cảm biến IR 4 ô để test giao diện Web User / Admin
khi chưa cắm mạch ESP32 và Camera thật (gọi trực tiếp GateDataService của Việt như luồng của Duy).

Cách dùng:
  1. Đặt chỗ trên Web User (ví dụ xe 43A12345 đặt ô B1) -> Bước 1: Reserved
  2. Chạy từng bước:
     edge-server\.venv\Scripts\python.exe edge-server\scripts\simulate_gate_flow.py --step checkin
     edge-server\.venv\Scripts\python.exe edge-server\scripts\simulate_gate_flow.py --step enter
     edge-server\.venv\Scripts\python.exe edge-server\scripts\simulate_gate_flow.py --step park
     edge-server\.venv\Scripts\python.exe edge-server\scripts\simulate_gate_flow.py --step exit
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

_EDGE_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = _EDGE_ROOT / "src"
for _p in (_SRC_DIR, _EDGE_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from scripts.seed_demo_data import make_deterministic_l2_vector
from smart_parking.ai.plate.normalizer import PlateNormalizer
from smart_parking.application.services.gate_data_service import GateDataService
from smart_parking.config.settings import get_settings
from smart_parking.infrastructure.database.mysql_db import MySQLDatabase, utc_now
from smart_parking.infrastructure.database.unit_of_work import UnitOfWork
from smart_parking.infrastructure.security.embedding_cipher import EmbeddingCipher


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Giả lập luồng cổng vào/ra & cảm biến IR 4 ô trên MySQL để test giao diện Web User/Admin"
    )
    parser.add_argument(
        "--plate",
        type=str,
        default="43A12345",
        help="Biển số xe đang đặt chỗ / gửi xe (mặc định: 43A12345)",
    )
    parser.add_argument(
        "--step",
        type=str,
        required=True,
        choices=["checkin", "enter", "park", "exit"],
        help="Bước cần giả lập: checkin (đến cổng IN) | enter (qua cổng IN) | park (IR báo đã đỗ) | exit (ra cổng OUT)",
    )
    args = parser.parse_args()

    plate = PlateNormalizer.normalize(args.plate)
    settings = get_settings()
    db = MySQLDatabase(settings)
    uow = UnitOfWork(db)
    cipher = EmbeddingCipher(
        secret_key=settings.embedding_secret_key,
        default_key_version=settings.embedding_key_version,
    )
    gate_svc = GateDataService(uow=uow, cipher=cipher, settings=settings)
    now_dt = utc_now()

    if args.step == "checkin":
        event_id = f"SIM-IN-{uuid.uuid4().hex[:8]}"
        res = gate_svc.begin_booking_checkin(
            plate_number=plate,
            event_id=event_id,
            device_id="SIM_GATE_IN",
            now_utc=now_dt,
        )
        res_print = {k: v for k, v in res.items() if k != "reference_embedding"}
        print("[OK] Bước 2 (checkin) -> Booking đã chuyển sang Checkin_pending:")
        print(json.dumps(res_print, indent=2, ensure_ascii=False))
        print("=> Hãy bấm 'Làm mới' (hoặc F5) trên Web User để xem bước 2 sáng lên!")

    elif args.step == "enter":
        # Find active booking (Reserved or Checkin_pending)
        def _find_booking(tx):
            veh = tx.vehicles.get_by_plate(plate)
            if veh is None:
                raise RuntimeError(f"Không tìm thấy xe {plate}")
            return tx.bookings.find_active_by_vehicle(veh.vehicle_id)

        booking = uow.run_transactional(_find_booking, readonly=True)
        if booking is None:
            raise RuntimeError(
                f"Xe {plate} chưa có booking nào đang ở trạng thái Reserved hoặc Checkin_pending!"
            )

        event_id = booking.checkin_event_id or f"SIM-IN-{uuid.uuid4().hex[:8]}"
        if booking.status.value == "Reserved":
            gate_svc.begin_booking_checkin(
                plate_number=plate,
                event_id=event_id,
                device_id="SIM_GATE_IN",
                now_utc=now_dt,
            )

        perm = gate_svc.confirm_booking_entry_permission(
            booking_id=booking.booking_id,
            event_id=event_id,
            session_face_template_data={
                "embedding": make_deterministic_l2_vector(seed=20261118),
                "liveness_status": "Passed",
                "liveness_score": 0.96,
                "quality_score": 0.92,
            },
            command_id=f"SIM-CMD-{uuid.uuid4().hex[:6]}",
            ocr_confidence=0.99,
            now_utc=now_dt,
        )
        passed = gate_svc.confirm_gate_in_passage(event_id=event_id, now_utc=now_dt)
        print("[OK] Bước 3a (enter) -> Xe đã qua cổng IN (Checked_in, Session Active / Parking_pending):")
        print(json.dumps({"permission": perm, "passage": passed}, indent=2, ensure_ascii=False))
        print("=> Hãy bấm 'Làm mới' (hoặc F5) trên Web User để thấy trạng thái 'Đã qua cổng vào • Đang di chuyển vào ô'!")

    elif args.step == "park":
        def _find_session_and_slots(tx):
            sess = tx.sessions.find_live_by_plate(plate)
            slots = tx.slots.get_all_slots()
            return sess, slots

        sess, slots = uow.run_transactional(_find_session_and_slots, readonly=True)
        if sess is None:
            raise RuntimeError(f"Xe {plate} chưa có phiên gửi xe nào đang hoạt động (hãy chạy --step enter trước).")

        payload = {s.slot_id: s.physical_status.value for s in slots}
        payload[sess.assigned_slot_id] = "Occupied"
        max_seq = max((s.last_sequence or 0) for s in slots)
        snap = gate_svc.update_ir_slot_snapshot(
            device_id="SIM_ESP32_IR",
            boot_id="BOOT-SIM-DEMO",
            sequence=max_seq + 1,
            slots_payload=payload,
            received_at=now_dt,
        )
        print(f"[OK] Bước 3b (park) -> Cảm biến IR báo ô {sess.assigned_slot_id} = Occupied (Parked_confirmed):")
        print(json.dumps(snap, indent=2, ensure_ascii=False))
        print("=> Hãy bấm 'Làm mới' (hoặc F5) trên Web User để thấy trạng thái xanh '✓ XE ĐÃ ĐỖ ỔN ĐỊNH' & đồng hồ tính giờ đỗ!")

    elif args.step == "exit":
        event_id = f"SIM-OUT-{uuid.uuid4().hex[:8]}"
        prep = gate_svc.prepare_exit_verification(
            plate_number=plate,
            event_id=event_id,
            device_id="SIM_GATE_OUT",
            now_utc=now_dt,
        )
        gate_svc.approve_exit_permission(
            session_id=prep["session_id"],
            event_id=event_id,
            command_id=f"SIM-OUT-CMD-{uuid.uuid4().hex[:6]}",
            liveness_status="Passed",
            liveness_score=0.95,
            similarity_score=0.99,
            now_utc=now_dt,
        )
        closed = gate_svc.confirm_gate_out_passage(event_id=event_id, now_utc=now_dt)

        def _get_slots(tx):
            return tx.slots.get_all_slots()

        slots = uow.run_transactional(_get_slots, readonly=True)
        payload = {s.slot_id: s.physical_status.value for s in slots}
        payload[prep["assigned_slot_id"]] = "Free"
        max_seq = max((s.last_sequence or 0) for s in slots)
        gate_svc.update_ir_slot_snapshot(
            device_id="SIM_ESP32_IR",
            boot_id="BOOT-SIM-DEMO",
            sequence=max_seq + 1,
            slots_payload=payload,
            received_at=now_dt,
        )
        print(f"[OK] Bước 4 (exit) -> Xe {plate} đã ra cổng OUT (Closed / Completed), ô {prep['assigned_slot_id']} đã trống:")
        print(json.dumps(closed, indent=2, ensure_ascii=False))
        print("=> Hãy bấm 'Làm mới' (hoặc F5) trên Web User để thấy ô xanh trở lại và lịch sử gửi xe đã lưu hoàn tất!")


if __name__ == "__main__":
    main()
