"""Gate and session data service for gate/IR orchestration and AI integration."""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np

from smart_parking.ai.plate.normalizer import PlateNormalizer
from smart_parking.application.services.event_service import RealtimeEventBus
from smart_parking.config.constants import (
    DEFAULT_FACE_CONFIG_VERSION,
    DEFAULT_FACE_DIMENSION,
    DEFAULT_FACE_DTYPE,
    DEFAULT_FACE_MODEL_ID,
    DEFAULT_FACE_MODEL_VERSION,
    SLOT_IDS,
)
from smart_parking.config.settings import Settings, get_settings
from smart_parking.domain.enums import (
    AccountStatus,
    BookingStatus,
    FaceTemplateStatus,
    GateDecision,
    GateId,
    LivenessStatus,
    LogEventType,
    ParkingStatus,
    PassageStatus,
    PhysicalSlotStatus,
    SessionStatus,
    UserRole,
)
from smart_parking.domain.exceptions import (
    AuthorizationException,
    BookingConflictException,
    DomainException,
    GateOperationException,
    ResourceNotFoundException,
    SessionNotFoundException,
    SlotNotAvailableException,
)
from smart_parking.infrastructure.database.mysql_db import format_utc_iso, format_vn_iso, utc_now
from smart_parking.infrastructure.database.unit_of_work import UnitOfWork
from smart_parking.infrastructure.security.embedding_cipher import EmbeddingCipher


class GateDataService:
    """
    Transactional data coordination layer for Gate IN, Gate OUT, IR 4-slot snapshots,
    and Manual Review decisions.
    Never holds a DB transaction while waiting for camera capture, AI inference, or physical passage.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        cipher: EmbeddingCipher,
        event_bus: Optional[RealtimeEventBus] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.uow = uow
        self.cipher = cipher
        self.event_bus = event_bus or RealtimeEventBus()
        self.settings = settings or get_settings()

    def _encrypt_face_payload(self, face_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate & encrypt 512-D float32 L2-normalized embedding from the AI payload."""
        raw_vec = face_data.get("embedding")
        if raw_vec is None:
            raw_vec = face_data.get("vector_np")
        if raw_vec is None:
            raise DomainException(
                "Thiếu vector khuôn mặt 512-D hợp lệ để tạo mẫu phiên.",
                reason_code="MISSING_FACE_EMBEDDING",
            )
        vec_np = np.asarray(raw_vec, dtype=np.float32).reshape(-1)
        key_version = str(face_data.get("key_version") or self.settings.embedding_key_version)
        blob, enc_meta = self.cipher.encrypt_embedding(vec_np, key_version=key_version)

        liveness_status = str(face_data.get("liveness_status") or LivenessStatus.PASSED.value)
        liveness_score = face_data.get("liveness_score")
        if liveness_status == LivenessStatus.NOT_USED.value:
            liveness_score = None
        elif liveness_score is not None:
            liveness_score = float(liveness_score)

        quality_score = face_data.get("quality_score")
        if quality_score is not None:
            quality_score = float(quality_score)

        return {
            "embedding_blob": blob,
            "key_version": key_version,
            "encryption_metadata": enc_meta,
            "model_id": str(face_data.get("model_id") or DEFAULT_FACE_MODEL_ID),
            "model_version": str(face_data.get("model_version") or DEFAULT_FACE_MODEL_VERSION),
            "config_version": str(face_data.get("config_version") or DEFAULT_FACE_CONFIG_VERSION),
            "liveness_status": liveness_status,
            "liveness_score": liveness_score,
            "quality_score": quality_score,
            "embedding_size": DEFAULT_FACE_DIMENSION,
            "embedding_dtype": DEFAULT_FACE_DTYPE,
        }

    def begin_booking_checkin(
        self,
        plate_number: str,
        event_id: str,
        device_id: str = "GATE_IN",
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Step 1 of pre-booked vehicle arrival at Gate IN:
        - Find valid 'Reserved' booking (`expires_at > now_utc`) by normalized plate_number.
        - Lock vehicles (1) -> parking_slots (2) -> bookings (3) in strict order.
        - Transition booking to 'Checkin_pending', set checkin_started_at = now_utc, checkin_event_id = event_id.
        - Return booking metadata matched by plate. The live entry face belongs to the new session.
        """
        norm_plate = PlateNormalizer.normalize(plate_number)
        now_dt = now_utc or utc_now()

        def _tx(tx) -> Dict[str, Any]:
            # LOCK 1: vehicles
            vehicle = tx.vehicles.lock_by_plate_for_update(norm_plate)
            if vehicle is None:
                raise ResourceNotFoundException(
                    f"Biển số {norm_plate} chưa đăng ký phương tiện định danh.",
                    reason_code="VEHICLE_NOT_REGISTERED",
                )

            candidate = tx.bookings.find_active_by_vehicle(vehicle.vehicle_id)
            if candidate is None:
                raise ResourceNotFoundException(
                    f"Không tìm thấy đặt chỗ đang hiệu lực cho biển số {norm_plate}.",
                    reason_code="BOOKING_NOT_FOUND",
                )

            # LOCK 2: parking_slots
            slot = tx.slots.lock_by_id_for_update(candidate.slot_id)
            if slot is None:
                raise ResourceNotFoundException("Không tìm thấy ô đỗ của booking.", reason_code="SLOT_NOT_FOUND")

            # LOCK 3: bookings
            booking = tx.bookings.lock_by_id_for_update(candidate.booking_id)
            assert booking is not None

            # Idempotency check if same event_id retries begin_booking_checkin
            if booking.status == BookingStatus.CHECKIN_PENDING and booking.checkin_event_id == event_id:
                return {
                    "booking": booking,
                    "vehicle": vehicle,
                }

            if booking.status != BookingStatus.RESERVED:
                raise BookingConflictException(
                    f"Booking không ở trạng thái Reserved (hiện tại: {booking.status.value}).",
                    reason_code="BOOKING_INVALID_STATE_FOR_CHECKIN",
                )
            if booking.expires_at <= now_dt:
                raise BookingConflictException(
                    "Đặt chỗ đã quá thời hạn 60 phút.",
                    reason_code="BOOKING_ALREADY_EXPIRED",
                )

            # Ensure gate_events row exists before linking booking.checkin_event_id FK
            tx.gate_events.create_if_not_exists(
                event_id=event_id,
                gate_id=GateId.IN.value,
                device_id=device_id,
                decision=GateDecision.PENDING.value,
                passage_status=PassageStatus.WAITING.value,
                booking_id=booking.booking_id,
                created_at=now_dt,
            )

            tx.bookings.mark_checkin_pending(
                booking_id=booking.booking_id,
                event_id=event_id,
                now_utc=now_dt,
            )

            updated_booking = tx.bookings.get_by_id(booking.booking_id)
            assert updated_booking is not None
            return {
                "booking": updated_booking,
                "vehicle": vehicle,
            }

        tx_res = self.uow.run_transactional(_tx)
        booking = tx_res["booking"]
        return {
            "booking_id": booking.booking_id,
            "user_id": booking.user_id,
            "vehicle_id": booking.vehicle_id,
            "plate_number": tx_res["vehicle"].plate_number,
            "slot_id": booking.slot_id,
            "status": booking.status.value,
            "checkin_event_id": event_id,
        }

    def confirm_booking_entry_permission(
        self,
        booking_id: str,
        event_id: str,
        session_face_template_data: Dict[str, Any],
        command_id: Optional[str] = None,
        ocr_confidence: Optional[float] = None,
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Step 2 of pre-booked vehicle arrival after 1:1 face + liveness passes:
        - Lock vehicles (1) -> parking_slots (2) -> bookings (3) -> sessions (4) -> gate_events (5).
        - Verify slot is still held by booking_id, reference user template has not been revoked,
          and vehicle does not have a live session (`live_plate`).
        - Create `sessions` (`status = 'Entry_pending'`, `parking_status = 'Not_arrived'`, `assigned_slot_id = booking.slot_id`).
        - Store encrypted `session_face_templates` specifically for this session (T07).
        - Set `parking_slots.reserved_session_id = session_id` while keeping `active_booking_id` until gate passage.
        - Update `gate_events` (`decision = 'Approved'`, `command_id`).
        """
        now_dt = now_utc or utc_now()
        cmd_id = command_id or str(uuid.uuid4())
        enc_face = self._encrypt_face_payload(session_face_template_data)

        def _tx(tx) -> Dict[str, Any]:
            candidate = tx.bookings.get_by_id(booking_id)
            if candidate is None:
                raise ResourceNotFoundException("Không tìm thấy booking.", reason_code="BOOKING_NOT_FOUND")

            # LOCK 1: vehicles
            vehicle = tx.vehicles.lock_by_id_for_update(candidate.vehicle_id)
            if vehicle is None or vehicle.status != AccountStatus.ACTIVE:
                raise GateOperationException("Phương tiện không hợp lệ.", reason_code="VEHICLE_INACTIVE")

            # LOCK 2: parking_slots
            slot = tx.slots.lock_by_id_for_update(candidate.slot_id)
            if slot is None:
                raise ResourceNotFoundException("Không tìm thấy ô đỗ.", reason_code="SLOT_NOT_FOUND")

            # LOCK 3: bookings
            booking = tx.bookings.lock_by_id_for_update(booking_id)
            assert booking is not None

            # Idempotency check if session already created for this booking
            existing_session = tx.sessions.find_by_booking_id(booking_id)
            if existing_session is not None:
                return {
                    "session_id": existing_session.session_id,
                    "booking_id": booking.booking_id,
                    "assigned_slot_id": existing_session.assigned_slot_id,
                    "plate_number": existing_session.plate_number,
                    "status": existing_session.status.value,
                    "parking_status": existing_session.parking_status.value,
                    "command_id": cmd_id,
                    "event_id": event_id,
                }

            if booking.status not in (BookingStatus.CHECKIN_PENDING, BookingStatus.RESERVED):
                raise BookingConflictException(
                    f"Trạng thái booking '{booking.status.value}' không hợp lệ để cấp quyền vào cổng.",
                    reason_code="BOOKING_NOT_CHECKIN_PENDING",
                )
            if slot.active_booking_id != booking.booking_id or slot.reserved_session_id is not None:
                raise SlotNotAvailableException(
                    f"Ô {slot.slot_id} không còn giữ quyền hợp lệ cho booking {booking_id}.",
                    reason_code="SLOT_HOLD_LOST",
                )

            # LOCK 4: sessions (check no live_plate exists)
            live_sess = tx.sessions.lock_live_by_plate_for_update(vehicle.plate_number)
            if live_sess is not None:
                raise GateOperationException(
                    f"Biển số {vehicle.plate_number} đang có phiên hoạt động {live_sess.session_id}.",
                    reason_code="DUPLICATE_LIVE_PLATE_SESSION",
                )

            session_id = str(uuid.uuid4())
            session = tx.sessions.create(
                session_id=session_id,
                plate_number=vehicle.plate_number,
                user_id=booking.user_id,
                vehicle_id=vehicle.vehicle_id,
                booking_id=booking.booking_id,
                assigned_slot_id=booking.slot_id,
                status=SessionStatus.ENTRY_PENDING.value,
                parking_status=ParkingStatus.NOT_ARRIVED.value,
                ocr_confidence=ocr_confidence,
                entry_time=None,
                now_utc=now_dt,
            )

            tx.face_templates.create_session_template(
                session_id=session_id,
                embedding_blob=enc_face["embedding_blob"],
                key_version=enc_face["key_version"],
                encryption_metadata=enc_face["encryption_metadata"],
                model_id=enc_face["model_id"],
                model_version=enc_face["model_version"],
                config_version=enc_face["config_version"],
                liveness_status=enc_face["liveness_status"],
                liveness_score=enc_face["liveness_score"],
                quality_score=enc_face["quality_score"],
                embedding_size=enc_face["embedding_size"],
                embedding_dtype=enc_face["embedding_dtype"],
                captured_at=now_dt,
                expires_at=None,
            )

            # Hold reserved_session_id on parking_slots while KEEPING active_booking_id until physical passage
            tx.slots.assign_session(slot_id=slot.slot_id, session_id=session_id, now_utc=now_dt)

            # LOCK 5 / update: gate_events
            tx.gate_events.create_if_not_exists(
                event_id=event_id,
                gate_id=GateId.IN.value,
                device_id="GATE_IN",
                session_id=session_id,
                booking_id=booking.booking_id,
                decision=GateDecision.APPROVED.value,
                passage_status=PassageStatus.WAITING.value,
                reason_code="BOOKING_ENTRY_APPROVED",
                liveness_status=enc_face["liveness_status"],
                liveness_score=enc_face["liveness_score"],
                liveness_model_version=enc_face["model_version"],
                face_config_version=enc_face["config_version"],
                command_id=cmd_id,
                created_at=now_dt,
                decided_at=now_dt,
            )
            tx.gate_events.lock_by_id_for_update(event_id)
            tx.gate_events.update_decision(
                event_id=event_id,
                decision=GateDecision.APPROVED.value,
                reason_code="BOOKING_ENTRY_APPROVED",
                session_id=session_id,
                booking_id=booking.booking_id,
                command_id=cmd_id,
                liveness_status=enc_face["liveness_status"],
                liveness_score=enc_face["liveness_score"],
                liveness_model_version=enc_face["model_version"],
                face_config_version=enc_face["config_version"],
                decided_at=now_dt,
            )

            tx.parking_logs.append(
                event_type=LogEventType.GATE_IN.value,
                reason_code="BOOKING_ENTRY_APPROVED",
                event_id=event_id,
                session_id=session_id,
                actor_user_id=booking.user_id,
                details={
                    "booking_id": booking.booking_id,
                    "slot_id": slot.slot_id,
                    "plate_number": vehicle.plate_number,
                    "command_id": cmd_id,
                },
                created_at=now_dt,
            )

            return {
                "session_id": session.session_id,
                "booking_id": booking.booking_id,
                "assigned_slot_id": session.assigned_slot_id,
                "plate_number": session.plate_number,
                "status": session.status.value,
                "parking_status": session.parking_status.value,
                "command_id": cmd_id,
                "event_id": event_id,
            }

        res = self.uow.run_transactional(_tx)
        self.event_bus.publish("GATE_IN_APPROVED", res, now_utc=now_dt)
        return res

    def allocate_walkin_entry(
        self,
        plate_number: str,
        event_id: str,
        session_face_template_data: Dict[str, Any],
        command_id: Optional[str] = None,
        device_id: str = "GATE_IN",
        ocr_confidence: Optional[float] = None,
        deterministic_choice: bool = False,
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Walk-in vehicle entry allocation:
        - Checks plate_number has no live session (`live_plate`).
        - Locks all 4 slots in `parking_slots` (`FOR UPDATE`) and chooses an `available(slot)`
          (never picking a slot that is `Reserved`, `Assigned`, `Occupied`, `Unknown`, `Fault`, or stale! T01 & T02).
        - Creates `sessions` (`Entry_pending`), stores encrypted `session_face_templates`,
          sets `parking_slots.reserved_session_id = session_id`, updates `gate_events`.
        """
        norm_plate = PlateNormalizer.normalize(plate_number)
        now_dt = now_utc or utc_now()
        stale_sec = self.settings.slot_stale_seconds
        cmd_id = command_id or str(uuid.uuid4())
        enc_face = self._encrypt_face_payload(session_face_template_data)

        def _tx(tx) -> Dict[str, Any]:
            # Check idempotency by event_id
            existing_ev = tx.gate_events.get_by_id(event_id)
            if existing_ev is not None and existing_ev.session_id is not None:
                existing_sess = tx.sessions.get_by_id(existing_ev.session_id)
                if existing_sess is not None:
                    return {
                        "session_id": existing_sess.session_id,
                        "assigned_slot_id": existing_sess.assigned_slot_id,
                        "plate_number": existing_sess.plate_number,
                        "status": existing_sess.status.value,
                        "parking_status": existing_sess.parking_status.value,
                        "command_id": existing_ev.command_id or cmd_id,
                        "event_id": event_id,
                    }

            # LOCK 1 (optional): check if plate belongs to a registered user vehicle
            reg_vehicle = tx.vehicles.lock_by_plate_for_update(norm_plate)

            # LOCK 2: parking_slots (all 4 slots)
            all_slots = tx.slots.lock_all_slots_for_update()

            # LOCK 4: sessions (verify no live session for this plate)
            live_sess = tx.sessions.lock_live_by_plate_for_update(norm_plate)
            if live_sess is not None:
                raise GateOperationException(
                    f"Biển số {norm_plate} đang có phiên chưa kết thúc ({live_sess.session_id}).",
                    reason_code="DUPLICATE_LIVE_PLATE_SESSION",
                )

            available_slots = [s for s in all_slots if s.is_available(now_dt, stale_sec)]
            if not available_slots:
                raise SlotNotAvailableException(
                    "Bãi đỗ hiện không còn ô trống khả dụng cho khách vãng lai.",
                    reason_code="ERR_PARKING_FULL",
                )

            chosen_slot = (
                available_slots[0]
                if deterministic_choice
                else random.choice(available_slots)
            )

            session_id = str(uuid.uuid4())
            session = tx.sessions.create(
                session_id=session_id,
                plate_number=norm_plate,
                user_id=reg_vehicle.user_id if reg_vehicle else None,
                vehicle_id=reg_vehicle.vehicle_id if reg_vehicle else None,
                booking_id=None,
                assigned_slot_id=chosen_slot.slot_id,
                status=SessionStatus.ENTRY_PENDING.value,
                parking_status=ParkingStatus.NOT_ARRIVED.value,
                ocr_confidence=ocr_confidence,
                entry_time=None,
                now_utc=now_dt,
            )

            tx.face_templates.create_session_template(
                session_id=session_id,
                embedding_blob=enc_face["embedding_blob"],
                key_version=enc_face["key_version"],
                encryption_metadata=enc_face["encryption_metadata"],
                model_id=enc_face["model_id"],
                model_version=enc_face["model_version"],
                config_version=enc_face["config_version"],
                liveness_status=enc_face["liveness_status"],
                liveness_score=enc_face["liveness_score"],
                quality_score=enc_face["quality_score"],
                embedding_size=enc_face["embedding_size"],
                embedding_dtype=enc_face["embedding_dtype"],
                captured_at=now_dt,
                expires_at=None,
            )

            tx.slots.assign_session(
                slot_id=chosen_slot.slot_id,
                session_id=session_id,
                now_utc=now_dt,
            )

            tx.gate_events.create_if_not_exists(
                event_id=event_id,
                gate_id=GateId.IN.value,
                device_id=device_id,
                session_id=session_id,
                booking_id=None,
                decision=GateDecision.APPROVED.value,
                passage_status=PassageStatus.WAITING.value,
                reason_code="WALKIN_ENTRY_APPROVED",
                liveness_status=enc_face["liveness_status"],
                liveness_score=enc_face["liveness_score"],
                liveness_model_version=enc_face["model_version"],
                face_config_version=enc_face["config_version"],
                command_id=cmd_id,
                created_at=now_dt,
                decided_at=now_dt,
            )

            tx.parking_logs.append(
                event_type=LogEventType.GATE_IN.value,
                reason_code="WALKIN_ENTRY_APPROVED",
                event_id=event_id,
                session_id=session_id,
                actor_user_id=reg_vehicle.user_id if reg_vehicle else None,
                details={
                    "assigned_slot_id": chosen_slot.slot_id,
                    "plate_number": norm_plate,
                    "command_id": cmd_id,
                },
                created_at=now_dt,
            )

            return {
                "session_id": session.session_id,
                "assigned_slot_id": session.assigned_slot_id,
                "plate_number": session.plate_number,
                "status": session.status.value,
                "parking_status": session.parking_status.value,
                "command_id": cmd_id,
                "event_id": event_id,
            }

        res = self.uow.run_transactional(_tx)
        self.event_bus.publish("GATE_IN_WALKIN_APPROVED", res, now_utc=now_dt)
        return res

    def confirm_gate_in_passage(
        self,
        event_id: str,
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Confirm physical passage through Gate IN (idempotent by `event_id` - T13):
        - Lock parking_slots (2) -> bookings (3) -> sessions (4) -> gate_events (5).
        - Transition `sessions.status = 'Active'`, `entry_time = now_utc`, `parking_status = 'Parking_pending'`.
        - If linked to booking: transition `bookings.status = 'Checked_in'`, `checked_in_at = now_utc`,
          and release `parking_slots.active_booking_id = NULL` while keeping `reserved_session_id`.
        """
        now_dt = now_utc or utc_now()

        def _tx(tx) -> Dict[str, Any]:
            ev_meta = tx.gate_events.get_by_id(event_id)
            if ev_meta is None or ev_meta.session_id is None:
                raise ResourceNotFoundException(
                    f"Không tìm thấy sự kiện cổng vào {event_id}.",
                    reason_code="GATE_EVENT_NOT_FOUND",
                )
            sess_meta = tx.sessions.get_by_id(ev_meta.session_id)
            if sess_meta is None:
                raise SessionNotFoundException()

            # Idempotency check (T13): if already confirmed, return existing state without overwriting entry_time!
            if ev_meta.passage_status == PassageStatus.CONFIRMED and sess_meta.status == SessionStatus.ACTIVE:
                return {
                    "event_id": event_id,
                    "session_id": sess_meta.session_id,
                    "booking_id": sess_meta.booking_id,
                    "assigned_slot_id": sess_meta.assigned_slot_id,
                    "session_status": sess_meta.status.value,
                    "parking_status": sess_meta.parking_status.value,
                    "entry_time": format_utc_iso(sess_meta.entry_time),
                    "idempotent_replay": True,
                }

            # Canonical lock order: parking_slots (2) -> bookings (3) -> sessions (4) -> gate_events (5)
            tx.slots.lock_by_id_for_update(sess_meta.assigned_slot_id)
            booking = (
                tx.bookings.lock_by_id_for_update(sess_meta.booking_id)
                if sess_meta.booking_id
                else None
            )
            session = tx.sessions.lock_by_id_for_update(sess_meta.session_id)
            assert session is not None
            tx.gate_events.lock_by_id_for_update(event_id)

            tx.sessions.mark_entry_confirmed(session.session_id, now_utc=now_dt)
            if booking is not None:
                tx.bookings.mark_checked_in(booking.booking_id, now_utc=now_dt)
                # Remove active_booking_id from parking_slots while keeping reserved_session_id
                tx.slots.release_booking_if_matches(
                    slot_id=session.assigned_slot_id,
                    booking_id=booking.booking_id,
                    now_utc=now_dt,
                )

            tx.gate_events.confirm_passage(event_id=event_id, passed_at=now_dt)

            tx.parking_logs.append(
                event_type=LogEventType.GATE_IN.value,
                reason_code="GATE_IN_PASSAGE_CONFIRMED",
                event_id=event_id,
                session_id=session.session_id,
                actor_user_id=session.user_id,
                details={
                    "assigned_slot_id": session.assigned_slot_id,
                    "booking_id": session.booking_id,
                    "plate_number": session.plate_number,
                },
                created_at=now_dt,
            )

            updated_sess = tx.sessions.get_by_id(session.session_id)
            assert updated_sess is not None
            return {
                "event_id": event_id,
                "session_id": updated_sess.session_id,
                "booking_id": updated_sess.booking_id,
                "assigned_slot_id": updated_sess.assigned_slot_id,
                "session_status": updated_sess.status.value,
                "parking_status": updated_sess.parking_status.value,
                "entry_time": format_utc_iso(updated_sess.entry_time),
                "idempotent_replay": False,
            }

        res = self.uow.run_transactional(_tx)
        if not res.get("idempotent_replay"):
            self.event_bus.publish("GATE_IN_PASSAGE_CONFIRMED", res, now_utc=now_dt)
        return res

    def update_ir_slot_snapshot(
        self,
        device_id: str,
        boot_id: str,
        sequence: int,
        slots_payload: Dict[str, str],
        received_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Process 4-slot IR sensor snapshot from ESP32 DevKit:
        - Deduplicate duplicate or stale sequence numbers within the same `boot_id`.
        - Update `physical_status`, `last_seen_at`, `last_sequence`, `last_boot_id` for A1..B2.
        - Correlate parking state for `Active` sessions in `Parking_pending`:
          * `Parking_pending` -> `Parked_confirmed` when the assigned slot transitions `Free -> Occupied`
            without ambiguous unreserved slot occupation.
          * `Parking_pending` -> `Parking_review_required` if an unexpected slot becomes `Occupied`
            (preserving `assigned_slot_id`).
          * `Parking_pending` -> `Parking_timeout` if elapsed time since `entry_time` exceeds threshold.
        """
        now_dt = received_at or utc_now()
        timeout_sec = self.settings.parking_confirm_timeout_seconds

        def _tx(tx) -> Dict[str, Any]:
            # LOCK 2: parking_slots (all 4 slots)
            current_slots = {s.slot_id: s for s in tx.slots.lock_all_slots_for_update()}

            # Check duplicate / stale sequence within the same boot_id
            sample_slot = next(iter(current_slots.values()), None)
            if (
                sample_slot is not None
                and sample_slot.last_boot_id == boot_id
                and sample_slot.last_sequence is not None
                and int(sequence) <= int(sample_slot.last_sequence)
            ):
                return {
                    "accepted": False,
                    "reason": "STALE_OR_DUPLICATE_SEQUENCE",
                    "boot_id": boot_id,
                    "sequence": sequence,
                    "updated_slots": [],
                    "session_transitions": [],
                }

            newly_occupied_slots: List[str] = []
            updated_slot_ids: List[str] = []

            for slot_id in SLOT_IDS:
                if slot_id not in slots_payload:
                    continue
                new_phys = str(slots_payload[slot_id])
                if new_phys not in (
                    PhysicalSlotStatus.FREE.value,
                    PhysicalSlotStatus.OCCUPIED.value,
                    PhysicalSlotStatus.UNKNOWN.value,
                    PhysicalSlotStatus.FAULT.value,
                ):
                    new_phys = PhysicalSlotStatus.FAULT.value

                old_slot = current_slots.get(slot_id)
                if (
                    old_slot is not None
                    and old_slot.physical_status != PhysicalSlotStatus.OCCUPIED
                    and new_phys == PhysicalSlotStatus.OCCUPIED.value
                ):
                    newly_occupied_slots.append(slot_id)

                tx.slots.update_ir_sensor(
                    slot_id=slot_id,
                    physical_status=new_phys,
                    boot_id=boot_id,
                    sequence=sequence,
                    seen_at=now_dt,
                )
                updated_slot_ids.append(slot_id)

            refreshed_slots = {s.slot_id: s for s in tx.slots.get_all_slots()}

            # LOCK 4: sessions waiting for parking confirmation
            pending_sessions = tx.sessions.lock_active_parking_pending_sessions()
            transitions: List[Dict[str, Any]] = []

            # Identify if any slot without an assigned session unexpectedly turned Occupied
            unassigned_newly_occupied = [
                sid
                for sid in newly_occupied_slots
                if refreshed_slots[sid].reserved_session_id is None
            ]

            for sess in pending_sessions:
                assigned_slot = refreshed_slots.get(sess.assigned_slot_id)
                if assigned_slot is None:
                    continue

                if (
                    assigned_slot.physical_status == PhysicalSlotStatus.OCCUPIED
                    and not unassigned_newly_occupied
                ):
                    tx.sessions.update_parking_status(
                        session_id=sess.session_id,
                        parking_status=ParkingStatus.PARKED_CONFIRMED.value,
                        now_utc=now_dt,
                    )
                    transitions.append({
                        "session_id": sess.session_id,
                        "assigned_slot_id": sess.assigned_slot_id,
                        "new_parking_status": ParkingStatus.PARKED_CONFIRMED.value,
                    })
                elif unassigned_newly_occupied:
                    tx.sessions.update_parking_status(
                        session_id=sess.session_id,
                        parking_status=ParkingStatus.PARKING_REVIEW_REQUIRED.value,
                        now_utc=now_dt,
                    )
                    transitions.append({
                        "session_id": sess.session_id,
                        "assigned_slot_id": sess.assigned_slot_id,
                        "new_parking_status": ParkingStatus.PARKING_REVIEW_REQUIRED.value,
                        "unexpected_occupied_slots": unassigned_newly_occupied,
                    })
                elif (
                    sess.entry_time is not None
                    and (now_dt - sess.entry_time) > timedelta(seconds=timeout_sec)
                ):
                    tx.sessions.update_parking_status(
                        session_id=sess.session_id,
                        parking_status=ParkingStatus.PARKING_TIMEOUT.value,
                        now_utc=now_dt,
                    )
                    transitions.append({
                        "session_id": sess.session_id,
                        "assigned_slot_id": sess.assigned_slot_id,
                        "new_parking_status": ParkingStatus.PARKING_TIMEOUT.value,
                    })

            tx.parking_logs.append(
                event_type=LogEventType.SLOT_UPDATE.value,
                reason_code="IR_SNAPSHOT_APPLIED",
                details={
                    "device_id": device_id,
                    "boot_id": boot_id,
                    "sequence": sequence,
                    "slots": slots_payload,
                    "session_transitions": transitions,
                },
                created_at=now_dt,
            )

            return {
                "accepted": True,
                "boot_id": boot_id,
                "sequence": sequence,
                "updated_slots": updated_slot_ids,
                "session_transitions": transitions,
            }

        res = self.uow.run_transactional(_tx)
        if res.get("accepted"):
            self.event_bus.publish("SLOT_IR_SNAPSHOT_UPDATED", res, now_utc=now_dt)
        return res

    def prepare_exit_verification(
        self,
        plate_number: str,
        event_id: str,
        device_id: str = "GATE_OUT",
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Step 1 of vehicle exit at Gate OUT:
        - Find live 'Active' (or 'Exit_pending') session by normalized plate_number.
        - Retrieve and decrypt the session's OWN face template from `session_face_templates`
          (STRICT RULE: NEVER use `user_face_templates` in place of the session entry template! T08).
        - Create `gate_events` row for Gate OUT.
        """
        norm_plate = PlateNormalizer.normalize(plate_number)
        now_dt = now_utc or utc_now()

        def _tx(tx) -> Dict[str, Any]:
            session = tx.sessions.find_live_by_plate(norm_plate)
            if session is None or session.status not in (SessionStatus.ACTIVE, SessionStatus.EXIT_PENDING):
                raise SessionNotFoundException(
                    f"Không tìm thấy phiên gửi xe đang hoạt động cho biển số {norm_plate}."
                )

            sess_tpl = tx.face_templates.get_session_template(session.session_id)
            if sess_tpl is None:
                raise GateOperationException(
                    f"Phiên {session.session_id} không có mẫu khuôn mặt phiên (session_face_templates) để đối sánh.",
                    reason_code="SESSION_FACE_TEMPLATE_MISSING",
                )

            tx.gate_events.create_if_not_exists(
                event_id=event_id,
                gate_id=GateId.OUT.value,
                device_id=device_id,
                session_id=session.session_id,
                booking_id=session.booking_id,
                decision=GateDecision.PENDING.value,
                passage_status=PassageStatus.WAITING.value,
                created_at=now_dt,
            )

            return {
                "session": session,
                "session_template": sess_tpl,
            }

        tx_res = self.uow.run_transactional(_tx)
        sess_tpl = tx_res["session_template"]
        entry_vector = self.cipher.decrypt_embedding(
            blob=sess_tpl.embedding_blob,
            metadata=sess_tpl.encryption_metadata,
            dtype=sess_tpl.embedding_dtype,
            size=sess_tpl.embedding_size,
            key_version=sess_tpl.key_version,
        )
        session = tx_res["session"]
        return {
            "event_id": event_id,
            "session_id": session.session_id,
            "booking_id": session.booking_id,
            "plate_number": session.plate_number,
            "assigned_slot_id": session.assigned_slot_id,
            "status": session.status.value,
            "session_template_id": sess_tpl.template_id,
            "template_source": "session_face_templates",
            "entry_embedding": entry_vector,
            "model_id": sess_tpl.model_id,
            "model_version": sess_tpl.model_version,
        }

    def approve_exit_permission(
        self,
        session_id: str,
        event_id: str,
        command_id: Optional[str] = None,
        liveness_status: str = LivenessStatus.PASSED.value,
        liveness_score: Optional[float] = None,
        similarity_score: Optional[float] = None,
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Step 2 of vehicle exit after 1:1 session face match passes:
        - Transition `sessions.status = 'Exit_pending'`.
        - Keep `parking_slots.reserved_session_id = session_id` until Gate OUT passage is confirmed (T15).
        - Update `gate_events` (`decision = 'Approved'`, `command_id`).
        """
        now_dt = now_utc or utc_now()
        cmd_id = command_id or str(uuid.uuid4())

        def _tx(tx) -> Dict[str, Any]:
            sess_meta = tx.sessions.get_by_id(session_id)
            if sess_meta is None:
                raise SessionNotFoundException()

            # Canonical lock order: parking_slots (2) -> bookings (3) -> sessions (4) -> gate_events (5)
            tx.slots.lock_by_id_for_update(sess_meta.assigned_slot_id)
            if sess_meta.booking_id:
                tx.bookings.lock_by_id_for_update(sess_meta.booking_id)
            session = tx.sessions.lock_by_id_for_update(session_id)
            assert session is not None

            tx.sessions.mark_exit_pending(session.session_id, now_utc=now_dt)

            tx.gate_events.create_if_not_exists(
                event_id=event_id,
                gate_id=GateId.OUT.value,
                device_id="GATE_OUT",
                session_id=session.session_id,
                booking_id=session.booking_id,
                decision=GateDecision.APPROVED.value,
                passage_status=PassageStatus.WAITING.value,
                reason_code="EXIT_FACE_MATCH_APPROVED",
                liveness_status=liveness_status,
                liveness_score=liveness_score,
                command_id=cmd_id,
                created_at=now_dt,
                decided_at=now_dt,
            )
            tx.gate_events.lock_by_id_for_update(event_id)
            tx.gate_events.update_decision(
                event_id=event_id,
                decision=GateDecision.APPROVED.value,
                reason_code="EXIT_FACE_MATCH_APPROVED",
                session_id=session.session_id,
                booking_id=session.booking_id,
                command_id=cmd_id,
                liveness_status=liveness_status,
                liveness_score=liveness_score,
                decided_at=now_dt,
            )

            tx.parking_logs.append(
                event_type=LogEventType.GATE_OUT.value,
                reason_code="EXIT_FACE_MATCH_APPROVED",
                event_id=event_id,
                session_id=session.session_id,
                actor_user_id=session.user_id,
                details={
                    "plate_number": session.plate_number,
                    "assigned_slot_id": session.assigned_slot_id,
                    "similarity_score": similarity_score,
                    "command_id": cmd_id,
                },
                created_at=now_dt,
            )

            return {
                "event_id": event_id,
                "session_id": session.session_id,
                "assigned_slot_id": session.assigned_slot_id,
                "status": SessionStatus.EXIT_PENDING.value,
                "command_id": cmd_id,
            }

        res = self.uow.run_transactional(_tx)
        self.event_bus.publish("GATE_OUT_APPROVED", res, now_utc=now_dt)
        return res

    def confirm_gate_out_passage(
        self,
        event_id: str,
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Confirm physical passage through Gate OUT (idempotent by `event_id` - T13):
        - Lock parking_slots (2) -> bookings (3) -> sessions (4) -> gate_events (5).
        - Transition `sessions.status = 'Closed'`, record `exit_time = now_utc`.
        - Set `session_face_templates.expires_at` according to retention policy.
        - Release `parking_slots.reserved_session_id = NULL`.
        - Transition linked booking (if any) to `'Completed'`.
        """
        now_dt = now_utc or utc_now()
        retention_hours = self.settings.session_template_retention_hours

        def _tx(tx) -> Dict[str, Any]:
            ev_meta = tx.gate_events.get_by_id(event_id)
            if ev_meta is None or ev_meta.session_id is None:
                raise ResourceNotFoundException(
                    f"Không tìm thấy sự kiện cổng ra {event_id}.",
                    reason_code="GATE_EVENT_NOT_FOUND",
                )
            sess_meta = tx.sessions.get_by_id(ev_meta.session_id)
            if sess_meta is None:
                raise SessionNotFoundException()

            # Idempotency check (T13)
            if ev_meta.passage_status == PassageStatus.CONFIRMED and sess_meta.status == SessionStatus.CLOSED:
                return {
                    "event_id": event_id,
                    "session_id": sess_meta.session_id,
                    "booking_id": sess_meta.booking_id,
                    "assigned_slot_id": sess_meta.assigned_slot_id,
                    "session_status": sess_meta.status.value,
                    "exit_time": format_utc_iso(sess_meta.exit_time),
                    "idempotent_replay": True,
                }

            # Canonical lock order: parking_slots (2) -> bookings (3) -> sessions (4) -> gate_events (5)
            tx.slots.lock_by_id_for_update(sess_meta.assigned_slot_id)
            booking = (
                tx.bookings.lock_by_id_for_update(sess_meta.booking_id)
                if sess_meta.booking_id
                else None
            )
            session = tx.sessions.lock_by_id_for_update(sess_meta.session_id)
            assert session is not None
            tx.gate_events.lock_by_id_for_update(event_id)

            tx.sessions.mark_closed(session.session_id, now_utc=now_dt)
            tpl_expires_at = now_dt + timedelta(hours=retention_hours)
            tx.face_templates.set_session_template_expiry(
                session_id=session.session_id,
                expires_at=tpl_expires_at,
            )
            tx.slots.release_session_if_matches(
                slot_id=session.assigned_slot_id,
                session_id=session.session_id,
                now_utc=now_dt,
            )

            if booking is not None:
                tx.bookings.mark_completed(booking.booking_id, now_utc=now_dt)

            tx.gate_events.confirm_passage(event_id=event_id, passed_at=now_dt)

            tx.parking_logs.append(
                event_type=LogEventType.GATE_OUT.value,
                reason_code="GATE_OUT_PASSAGE_CONFIRMED",
                event_id=event_id,
                session_id=session.session_id,
                actor_user_id=session.user_id,
                details={
                    "assigned_slot_id": session.assigned_slot_id,
                    "booking_id": session.booking_id,
                    "plate_number": session.plate_number,
                    "template_expires_at": format_utc_iso(tpl_expires_at),
                },
                created_at=now_dt,
            )

            updated_sess = tx.sessions.get_by_id(session.session_id)
            assert updated_sess is not None
            return {
                "event_id": event_id,
                "session_id": updated_sess.session_id,
                "booking_id": updated_sess.booking_id,
                "assigned_slot_id": updated_sess.assigned_slot_id,
                "session_status": updated_sess.status.value,
                "exit_time": format_utc_iso(updated_sess.exit_time),
                "template_expires_at": format_utc_iso(tpl_expires_at),
                "idempotent_replay": False,
            }

        res = self.uow.run_transactional(_tx)
        if not res.get("idempotent_replay"):
            self.event_bus.publish("GATE_OUT_PASSAGE_CONFIRMED", res, now_utc=now_dt)
        return res

    def flag_gate_review_required(
        self,
        event_id: str,
        gate_id: str,
        device_id: str,
        reason_code: str,
        session_id: Optional[str] = None,
        booking_id: Optional[str] = None,
        liveness_status: Optional[str] = None,
        liveness_score: Optional[float] = None,
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Record a `Review_required` decision on `gate_events` without overwriting `sessions.status = 'Active'`."""
        now_dt = now_utc or utc_now()

        def _tx(tx) -> Dict[str, Any]:
            tx.gate_events.create_if_not_exists(
                event_id=event_id,
                gate_id=gate_id,
                device_id=device_id,
                session_id=session_id,
                booking_id=booking_id,
                decision=GateDecision.REVIEW_REQUIRED.value,
                passage_status=PassageStatus.WAITING.value,
                reason_code=reason_code,
                liveness_status=liveness_status,
                liveness_score=liveness_score,
                created_at=now_dt,
                decided_at=now_dt,
            )
            tx.gate_events.lock_by_id_for_update(event_id)
            ev = tx.gate_events.update_decision(
                event_id=event_id,
                decision=GateDecision.REVIEW_REQUIRED.value,
                reason_code=reason_code,
                session_id=session_id,
                booking_id=booking_id,
                liveness_status=liveness_status,
                liveness_score=liveness_score,
                decided_at=now_dt,
            )

            tx.parking_logs.append(
                event_type=LogEventType.MANUAL_REVIEW.value,
                reason_code=reason_code,
                event_id=event_id,
                session_id=session_id,
                details={
                    "gate_id": gate_id,
                    "decision": ev.decision.value,
                    "booking_id": booking_id,
                },
                created_at=now_dt,
            )
            return {
                "event_id": ev.event_id,
                "gate_id": ev.gate_id.value,
                "session_id": ev.session_id,
                "booking_id": ev.booking_id,
                "decision": ev.decision.value,
                "reason_code": ev.reason_code,
            }

        res = self.uow.run_transactional(_tx)
        self.event_bus.publish("MANUAL_REVIEW_REQUIRED", res, now_utc=now_dt)
        return res

    def record_manual_review_decision(
        self,
        event_id: str,
        admin_user_id: int,
        action: str,
        reason: str,
        command_id: Optional[str] = None,
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Record ADMIN manual review decision ('APPROVE' / 'APPROVED' or 'DENY' / 'DENIED' / 'REJECTED'):
        - Verify `admin_user_id` is an Active ADMIN.
        - Lock records in canonical order, prevent duplicate execution.
        - Record `reviewer_id`, `review_reason`, and `parking_logs` (`MANUAL_REVIEW`).
        - Never fabricate fake face embeddings or mark fake `FACE_ACCEPT`.
        """
        now_dt = now_utc or utc_now()
        clean_action = (action or "").strip().upper()
        if clean_action in ("APPROVE", "APPROVED"):
            new_decision = GateDecision.APPROVED.value
            reason_code = "MANUAL_REVIEW_APPROVED"
        elif clean_action in ("DENY", "DENIED", "REJECT", "REJECTED"):
            new_decision = GateDecision.DENIED.value
            reason_code = "MANUAL_REVIEW_DENIED"
        else:
            raise DomainException(
                f"Hành động duyệt thủ công '{action}' không hợp lệ (chỉ nhận APPROVE hoặc DENY).",
                reason_code="INVALID_REVIEW_ACTION",
            )

        clean_reason = (reason or "").strip() or "Quản trị viên phê duyệt thủ công"
        cmd_id = command_id or (str(uuid.uuid4()) if new_decision == GateDecision.APPROVED.value else None)

        def _tx(tx) -> Dict[str, Any]:
            admin_user = tx.users.get_by_id(admin_user_id)
            if (
                admin_user is None
                or admin_user.role != UserRole.ADMIN
                or admin_user.status != AccountStatus.ACTIVE
            ):
                raise AuthorizationException(
                    "Chỉ tài khoản ADMIN đang hoạt động mới có quyền duyệt ngoại lệ.",
                    reason_code="ADMIN_REQUIRED",
                )

            # Check if this is a parking anomaly synthetic ID (PARK-<session_id>)
            if event_id.startswith("PARK-"):
                sess_id = event_id[len("PARK-"):]
                sess_meta = tx.sessions.get_by_id(sess_id)
                if sess_meta is None:
                    raise SessionNotFoundException()
                tx.slots.lock_by_id_for_update(sess_meta.assigned_slot_id)
                sess = tx.sessions.lock_by_id_for_update(sess_id)
                assert sess is not None
                resolved_status = (
                    ParkingStatus.PARKED_CONFIRMED.value
                    if new_decision == GateDecision.APPROVED.value
                    else ParkingStatus.PARKING_REVIEW_REQUIRED.value
                )
                tx.sessions.update_parking_status(
                    session_id=sess.session_id,
                    parking_status=resolved_status,
                    now_utc=now_dt,
                )
                tx.parking_logs.append(
                    event_type=LogEventType.MANUAL_REVIEW.value,
                    reason_code=reason_code,
                    session_id=sess.session_id,
                    actor_user_id=admin_user.user_id,
                    details={
                        "review_type": "PARKING_ANOMALY",
                        "action": new_decision,
                        "reason": clean_reason,
                        "new_parking_status": resolved_status,
                    },
                    created_at=now_dt,
                )
                return {
                    "event_id": event_id,
                    "session_id": sess.session_id,
                    "decision": new_decision,
                    "reason_code": reason_code,
                    "reviewer_id": admin_user.user_id,
                    "review_reason": clean_reason,
                    "command_id": None,
                    "decided_at": format_utc_iso(now_dt),
                }

            ev_meta = tx.gate_events.get_by_id(event_id)
            if ev_meta is None:
                raise ResourceNotFoundException(
                    f"Không tìm thấy sự kiện cần duyệt {event_id}.",
                    reason_code="REVIEW_EVENT_NOT_FOUND",
                )

            # Canonical lock order if booking/session linked
            sess_meta = tx.sessions.get_by_id(ev_meta.session_id) if ev_meta.session_id else None
            booking_meta = tx.bookings.get_by_id(ev_meta.booking_id) if ev_meta.booking_id else None

            if booking_meta is not None:
                tx.vehicles.lock_by_id_for_update(booking_meta.vehicle_id)
                tx.slots.lock_by_id_for_update(booking_meta.slot_id)
                tx.bookings.lock_by_id_for_update(booking_meta.booking_id)
            elif sess_meta is not None:
                tx.slots.lock_by_id_for_update(sess_meta.assigned_slot_id)

            if sess_meta is not None:
                tx.sessions.lock_by_id_for_update(sess_meta.session_id)

            ev = tx.gate_events.lock_by_id_for_update(event_id)
            assert ev is not None

            # Prevent duplicate review command
            if ev.reviewer_id is not None and ev.decision in (GateDecision.APPROVED, GateDecision.DENIED):
                raise GateOperationException(
                    f"Sự kiện {event_id} đã được duyệt trước đó ({ev.decision.value}).",
                    reason_code="REVIEW_ALREADY_DECIDED",
                )

            updated_ev = tx.gate_events.record_manual_review(
                event_id=event_id,
                decision=new_decision,
                reviewer_id=admin_user.user_id,
                review_reason=clean_reason,
                reason_code=reason_code,
                command_id=cmd_id,
                decided_at=now_dt,
            )

            # IfGate OUT was approved manually, mark session Exit_pending; if denied on Gate IN Checkin_pending, revert booking to Reserved
            if new_decision == GateDecision.APPROVED.value and sess_meta is not None and ev.gate_id == GateId.OUT:
                tx.sessions.mark_exit_pending(sess_meta.session_id, now_utc=now_dt)
            elif new_decision == GateDecision.DENIED.value and booking_meta is not None and booking_meta.status == BookingStatus.CHECKIN_PENDING:
                tx.bookings.revert_checkin_pending_to_reserved(booking_meta.booking_id)

            tx.parking_logs.append(
                event_type=LogEventType.MANUAL_REVIEW.value,
                reason_code=reason_code,
                event_id=event_id,
                session_id=updated_ev.session_id,
                actor_user_id=admin_user.user_id,
                details={
                    "gate_id": updated_ev.gate_id.value,
                    "decision": updated_ev.decision.value,
                    "review_reason": clean_reason,
                    "command_id": updated_ev.command_id,
                },
                created_at=now_dt,
            )

            return {
                "event_id": updated_ev.event_id,
                "gate_id": updated_ev.gate_id.value,
                "session_id": updated_ev.session_id,
                "booking_id": updated_ev.booking_id,
                "decision": updated_ev.decision.value,
                "reason_code": updated_ev.reason_code,
                "reviewer_id": updated_ev.reviewer_id,
                "review_reason": updated_ev.review_reason,
                "command_id": updated_ev.command_id,
                "decided_at": format_utc_iso(updated_ev.decided_at),
            }

        res = self.uow.run_transactional(_tx)
        self.event_bus.publish("MANUAL_REVIEW_DECIDED", res, now_utc=now_dt)
        return res

    def update_user_face_template_offline(
        self,
        user_id: int,
        vector_np: np.ndarray,
        model_id: str = DEFAULT_FACE_MODEL_ID,
        model_version: str = DEFAULT_FACE_MODEL_VERSION,
        config_version: str = DEFAULT_FACE_CONFIG_VERSION,
        liveness_status: str = LivenessStatus.NOT_USED.value,
        liveness_score: Optional[float] = None,
        quality_score: Optional[float] = None,
        actor_user_id: Optional[int] = None,
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Internal maintenance tool API to update a user's reference face template (`user_face_templates`):
        - Marks previous `Active` user_face_template as `'Replaced'` with `revoked_at = now_utc`.
        - Inserts new `'Active'` user_face_template in the same transaction.
        - Enforces `liveness_status = 'Not_used'` and `liveness_score = None` for offline imports (T20).
        - Does NOT touch `session_face_templates` of any ongoing session (T08).
        """
        now_dt = now_utc or utc_now()
        if liveness_status == LivenessStatus.NOT_USED.value:
            liveness_score = None

        blob, enc_meta = self.cipher.encrypt_embedding(
            vector_np,
            key_version=self.settings.embedding_key_version,
        )

        def _tx(tx) -> Dict[str, Any]:
            tpl = tx.face_templates.upsert_active_user_template(
                user_id=user_id,
                embedding_blob=blob,
                key_version=self.settings.embedding_key_version,
                encryption_metadata=enc_meta,
                model_id=model_id,
                model_version=model_version,
                config_version=config_version,
                liveness_status=liveness_status,
                liveness_score=liveness_score,
                quality_score=quality_score,
                now_utc=now_dt,
            )
            tx.parking_logs.append(
                event_type=LogEventType.FACE_TEMPLATE_UPDATED.value,
                reason_code="USER_FACE_TEMPLATE_REPLACED",
                actor_user_id=actor_user_id,
                details={
                    "user_id": user_id,
                    "new_template_id": tpl.template_id,
                    "liveness_status": tpl.liveness_status.value,
                },
                created_at=now_dt,
            )
            return {
                "template_id": tpl.template_id,
                "user_id": tpl.user_id,
                "status": tpl.status.value,
                "liveness_status": tpl.liveness_status.value,
                "liveness_score": tpl.liveness_score,
                "created_at": format_utc_iso(tpl.created_at),
            }

        return self.uow.run_transactional(_tx)

    def deny_gate_event(
        self,
        event_id: str,
        gate_id: str,
        device_id: str,
        reason_code: str,
        booking_id: Optional[str] = None,
        session_id: Optional[str] = None,
        liveness_status: Optional[str] = None,
        liveness_score: Optional[float] = None,
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Record an automated Gate IN/OUT denial (e.g. face mismatch, liveness failed).
        If a booking was in 'Checkin_pending' without a created session, safely reverts it to
        'Reserved' (if unexpired) or 'Expired' (releasing active_booking_id if expired).
        """
        now_dt = now_utc or utc_now()

        def _tx(tx) -> Dict[str, Any]:
            booking_meta = tx.bookings.get_by_id(booking_id) if booking_id else None
            if booking_meta is not None:
                tx.vehicles.lock_by_id_for_update(booking_meta.vehicle_id)
                tx.slots.lock_by_id_for_update(booking_meta.slot_id)
                booking = tx.bookings.lock_by_id_for_update(booking_meta.booking_id)
                if booking is not None and booking.status == BookingStatus.CHECKIN_PENDING:
                    if tx.sessions.find_by_booking_id(booking.booking_id) is None:
                        if booking.expires_at > now_dt:
                            tx.bookings.revert_checkin_pending_to_reserved(booking.booking_id)
                        else:
                            tx.bookings.revert_checkin_pending_to_reserved(booking.booking_id)
                            tx.bookings.mark_expired(booking.booking_id)
                            tx.slots.release_booking_if_matches(
                                slot_id=booking.slot_id,
                                booking_id=booking.booking_id,
                                now_utc=now_dt,
                            )

            tx.gate_events.create_if_not_exists(
                event_id=event_id,
                gate_id=gate_id,
                device_id=device_id,
                session_id=session_id,
                booking_id=booking_id,
                decision=GateDecision.DENIED.value,
                passage_status=PassageStatus.CANCELLED.value,
                reason_code=reason_code,
                liveness_status=liveness_status,
                liveness_score=liveness_score,
                created_at=now_dt,
                decided_at=now_dt,
            )
            tx.gate_events.lock_by_id_for_update(event_id)
            ev = tx.gate_events.update_decision(
                event_id=event_id,
                decision=GateDecision.DENIED.value,
                reason_code=reason_code,
                session_id=session_id,
                booking_id=booking_id,
                liveness_status=liveness_status,
                liveness_score=liveness_score,
                decided_at=now_dt,
            )

            tx.parking_logs.append(
                event_type=LogEventType.GATE_IN.value if gate_id == GateId.IN.value else LogEventType.GATE_OUT.value,
                reason_code=reason_code,
                event_id=event_id,
                session_id=session_id,
                details={
                    "gate_id": gate_id,
                    "booking_id": booking_id,
                    "decision": ev.decision.value,
                },
                created_at=now_dt,
            )
            return {
                "event_id": ev.event_id,
                "gate_id": ev.gate_id.value,
                "decision": ev.decision.value,
                "reason_code": ev.reason_code,
                "booking_id": booking_id,
                "session_id": session_id,
            }

        res = self.uow.run_transactional(_tx)
        self.event_bus.publish("GATE_EVENT_DENIED", res, now_utc=now_dt)
        return res

    def cancel_unpassed_entry_session(
        self,
        event_id: str,
        reason_code: str = "ERR_GATE_TIMEOUT",
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Roll back an 'Entry_pending' session when Gate IN barrier opened but vehicle never passed:
        - Transitions session to 'Cancelled', schedules retention expiry on session_face_templates.
        - Releases parking_slots.reserved_session_id = NULL.
        - Reverts linked booking to 'Reserved' (if unexpired) or 'Expired' (and releases active_booking_id).
        """
        now_dt = now_utc or utc_now()
        retention_hours = self.settings.session_template_retention_hours

        def _tx(tx) -> Dict[str, Any]:
            ev_meta = tx.gate_events.get_by_id(event_id)
            if ev_meta is None or ev_meta.session_id is None:
                raise ResourceNotFoundException("Không tìm thấy sự kiện cổng vào.", reason_code="GATE_EVENT_NOT_FOUND")
            sess_meta = tx.sessions.get_by_id(ev_meta.session_id)
            if sess_meta is None:
                raise SessionNotFoundException()
            if sess_meta.status == SessionStatus.CANCELLED:
                return {
                    "event_id": event_id,
                    "session_id": sess_meta.session_id,
                    "session_status": sess_meta.status.value,
                    "idempotent_replay": True,
                }
            if sess_meta.status != SessionStatus.ENTRY_PENDING:
                raise GateOperationException(
                    f"Chỉ có thể hủy phiên chưa qua cổng ở trạng thái Entry_pending (hiện tại: {sess_meta.status.value}).",
                    reason_code="SESSION_NOT_ENTRY_PENDING",
                )

            if sess_meta.vehicle_id is not None:
                tx.vehicles.lock_by_id_for_update(sess_meta.vehicle_id)
            tx.slots.lock_by_id_for_update(sess_meta.assigned_slot_id)
            booking = (
                tx.bookings.lock_by_id_for_update(sess_meta.booking_id)
                if sess_meta.booking_id
                else None
            )
            session = tx.sessions.lock_by_id_for_update(sess_meta.session_id)
            assert session is not None
            tx.gate_events.lock_by_id_for_update(event_id)

            tx.sessions.mark_cancelled(session.session_id, now_utc=now_dt)
            tx.face_templates.set_session_template_expiry(
                session_id=session.session_id,
                expires_at=now_dt + timedelta(hours=retention_hours),
            )
            tx.slots.release_session_if_matches(
                slot_id=session.assigned_slot_id,
                session_id=session.session_id,
                now_utc=now_dt,
            )

            if booking is not None:
                if booking.expires_at > now_dt:
                    tx.bookings.revert_checkin_pending_to_reserved(booking.booking_id)
                else:
                    tx.bookings.revert_checkin_pending_to_reserved(booking.booking_id)
                    tx.bookings.mark_expired(booking.booking_id)
                    tx.slots.release_booking_if_matches(
                        slot_id=booking.slot_id,
                        booking_id=booking.booking_id,
                        now_utc=now_dt,
                    )

            tx.cursor.execute(
                "UPDATE gate_events SET passage_status = 'Cancelled', reason_code = %s WHERE event_id = %s",
                (reason_code, event_id),
            )
            tx.parking_logs.append(
                event_type=LogEventType.GATE_IN.value,
                reason_code=reason_code,
                event_id=event_id,
                session_id=session.session_id,
                actor_user_id=session.user_id,
                details={
                    "assigned_slot_id": session.assigned_slot_id,
                    "booking_id": session.booking_id,
                    "action": "ENTRY_SESSION_CANCELLED_NO_PASSAGE",
                },
                created_at=now_dt,
            )
            return {
                "event_id": event_id,
                "session_id": session.session_id,
                "assigned_slot_id": session.assigned_slot_id,
                "session_status": SessionStatus.CANCELLED.value,
                "idempotent_replay": False,
            }

        res = self.uow.run_transactional(_tx)
        if not res.get("idempotent_replay"):
            self.event_bus.publish("GATE_IN_ENTRY_CANCELLED", res, now_utc=now_dt)
        return res


# Alias as specified in prompt
SessionDataService = GateDataService
