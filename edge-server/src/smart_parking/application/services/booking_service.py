"""Booking Service: 60-minute slot reservation, cancellation, expiry worker, and history."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from smart_parking.ai.plate.normalizer import PlateNormalizer
from smart_parking.application.services.event_service import RealtimeEventBus
from smart_parking.config.constants import SLOT_IDS
from smart_parking.config.settings import Settings, get_settings
from smart_parking.domain.entities.booking import Booking
from smart_parking.domain.enums import (
    AccountStatus,
    BookingStatus,
    LogEventType,
    PhysicalSlotStatus,
    UserRole,
)
from smart_parking.domain.exceptions import (
    AuthorizationException,
    BookingConflictException,
    DomainException,
    ResourceNotFoundException,
    SlotNotAvailableException,
)
from smart_parking.infrastructure.database.mysql_db import format_utc_iso, format_vn_iso, utc_now
from smart_parking.infrastructure.database.unit_of_work import UnitOfWork


class BookingService:
    """
    Handles 60-minute parking slot bookings with short MySQL transactions and canonical lock ordering:
    1. vehicles -> 2. parking_slots -> 3. bookings -> 4. sessions
    """

    def __init__(
        self,
        uow: UnitOfWork,
        event_bus: Optional[RealtimeEventBus] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.uow = uow
        self.event_bus = event_bus or RealtimeEventBus()
        self.settings = settings or get_settings()
        # Thread-safe idempotency cache mapping (user_id, idempotency_key) -> booking_id
        self._idempotency_keys: Dict[tuple[int, str], str] = {}
        self._idempotency_lock = threading.Lock()

    def create_booking(
        self,
        user_id: int,
        vehicle_id: int,
        slot_id: str,
        idempotency_key: Optional[str] = None,
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Create a 60-minute booking for `slot_id` by `user_id` and `vehicle_id`.
        Enforces strict lock order: vehicles (1) -> parking_slots (2).
        """
        clean_slot_id = (slot_id or "").strip().upper()
        if clean_slot_id not in SLOT_IDS:
            raise DomainException(
                f"Mã ô đỗ '{slot_id}' không hợp lệ (chỉ chấp nhận A1, A2, B1, B2).",
                reason_code="INVALID_SLOT_ID",
                http_status=400,
            )

        now_dt = now_utc or utc_now()
        stale_sec = self.settings.slot_stale_seconds
        ttl_minutes = self.settings.booking_ttl_minutes

        # Check idempotency key before starting a new write
        clean_idem_key = idempotency_key.strip() if idempotency_key else None
        if clean_idem_key:
            with self._idempotency_lock:
                cached_booking_id = self._idempotency_keys.get((int(user_id), clean_idem_key))
            if cached_booking_id:
                existing_dto = self.get_booking_detail(
                    booking_id=cached_booking_id,
                    requester_user_id=user_id,
                    requester_role=UserRole.USER.value,
                    now_utc=now_dt,
                )
                return existing_dto

        def _tx(tx) -> Dict[str, Any]:
            # Validate user account is Active
            user = tx.users.get_by_id(user_id)
            if user is None or user.status != AccountStatus.ACTIVE:
                raise AuthorizationException(
                    "Tài khoản người dùng không hợp lệ hoặc đã bị khóa.",
                    reason_code="USER_INACTIVE",
                )

            # LOCK 1: vehicles (Rank 1)
            vehicle = tx.vehicles.lock_by_id_for_update(vehicle_id)
            if vehicle is None:
                raise ResourceNotFoundException("Không tìm thấy phương tiện.", reason_code="VEHICLE_NOT_FOUND")
            if int(vehicle.user_id) != int(user_id):
                raise AuthorizationException(
                    "Phương tiện không thuộc quyền sở hữu của tài khoản này.",
                    reason_code="VEHICLE_NOT_OWNED",
                )
            if vehicle.status != AccountStatus.ACTIVE:
                raise BookingConflictException(
                    "Phương tiện đang bị vô hiệu hóa, không thể đặt chỗ.",
                    reason_code="VEHICLE_DISABLED",
                )

            # LOCK 2: parking_slots (Rank 2)
            slot = tx.slots.lock_by_id_for_update(clean_slot_id)
            if slot is None:
                raise ResourceNotFoundException(
                    f"Không tìm thấy ô đỗ {clean_slot_id}.",
                    reason_code="SLOT_NOT_FOUND",
                )

            # Check 1: Does vehicle already have an active booking ('Reserved' or 'Checkin_pending')?
            active_booking = tx.bookings.find_active_by_vehicle(vehicle.vehicle_id)
            if active_booking is not None:
                raise BookingConflictException(
                    f"Xe {PlateNormalizer.format_display(vehicle.plate_number)} đang có đặt chỗ hiệu lực tại ô {active_booking.slot_id}.",
                    reason_code="VEHICLE_ALREADY_HAS_ACTIVE_BOOKING",
                    details={
                        "existing_booking_id": active_booking.booking_id,
                        "existing_slot_id": active_booking.slot_id,
                        "existing_status": active_booking.status.value,
                    },
                )

            # Check 2: Does plate_number already have an unclosed session ('Entry_pending', 'Active', 'Exit_pending')?
            live_session = tx.sessions.find_live_by_plate(vehicle.plate_number)
            if live_session is not None:
                raise BookingConflictException(
                    f"Xe {PlateNormalizer.format_display(vehicle.plate_number)} hiện đang có phiên gửi xe chưa kết thúc tại ô {live_session.assigned_slot_id}.",
                    reason_code="VEHICLE_ALREADY_IN_PARKING",
                    details={
                        "active_session_id": live_session.session_id,
                        "assigned_slot_id": live_session.assigned_slot_id,
                        "session_status": live_session.status.value,
                    },
                )

            # Check 3: Verify canonical availability formula available(slot)
            if not slot.is_available(now_dt, stale_sec):
                display_enum, label_vi = slot.compute_display_status(now_dt, stale_sec)
                if slot.active_booking_id is not None:
                    reason = "SLOT_ALREADY_RESERVED"
                    msg = f"Ô {clean_slot_id} vừa được đặt giữ chỗ bởi người dùng khác."
                elif slot.reserved_session_id is not None:
                    reason = "SLOT_ASSIGNED_TO_SESSION"
                    msg = f"Ô {clean_slot_id} đang được giữ cho phiên xe trong bãi."
                elif slot.physical_status == PhysicalSlotStatus.OCCUPIED:
                    reason = "SLOT_OCCUPIED"
                    msg = f"Ô {clean_slot_id} hiện đang có xe đỗ."
                else:
                    reason = "SLOT_SENSOR_STALE_OR_FAULT"
                    msg = f"Ô {clean_slot_id} chưa đủ dữ liệu cảm biến hợp lệ hoặc cảm biến lỗi ({label_vi})."

                raise SlotNotAvailableException(
                    message=msg,
                    reason_code=reason,
                    details={
                        "slot_id": slot.slot_id,
                        "physical_status": slot.physical_status.value,
                        "display_status": display_enum.value,
                        "label_vi": label_vi,
                        "is_available": False,
                    },
                )

            booking_id = str(uuid.uuid4())
            expires_at = now_dt + timedelta(minutes=ttl_minutes)
            booking = tx.bookings.create(
                booking_id=booking_id,
                user_id=user.user_id,
                vehicle_id=vehicle.vehicle_id,
                slot_id=slot.slot_id,
                status=BookingStatus.RESERVED.value,
                created_at=now_dt,
                expires_at=expires_at,
            )
            booking.plate_number = vehicle.plate_number

            tx.slots.assign_booking(slot_id=slot.slot_id, booking_id=booking_id, now_utc=now_dt)

            tx.parking_logs.append(
                event_type=LogEventType.BOOKING_CREATED.value,
                reason_code="USER_BOOKED_SLOT_60M",
                actor_user_id=user.user_id,
                details={
                    "booking_id": booking_id,
                    "slot_id": slot.slot_id,
                    "vehicle_id": vehicle.vehicle_id,
                    "plate_number": vehicle.plate_number,
                    "expires_at": format_utc_iso(expires_at),
                },
                created_at=now_dt,
            )

            return self._booking_to_dto(booking, now_dt)

        try:
            result_dto = self.uow.run_transactional(_tx)
        except Exception as exc:
            errno = getattr(exc, "errno", None)
            msg_low = str(exc).lower()
            if errno == 1062 or "duplicate entry" in msg_low or "unique constraint failed" in msg_low:
                if "active_vehicle" in msg_low:
                    raise BookingConflictException(
                        "Xe của bạn đã có một đặt chỗ đang hiệu lực.",
                        reason_code="VEHICLE_ALREADY_HAS_ACTIVE_BOOKING",
                    ) from exc
                raise SlotNotAvailableException(
                    f"Ô {clean_slot_id} vừa được đặt bởi người dùng khác.",
                    reason_code="SLOT_ALREADY_RESERVED",
                ) from exc
            raise

        if clean_idem_key:
            with self._idempotency_lock:
                self._idempotency_keys[(int(user_id), clean_idem_key)] = result_dto["booking_id"]

        # Broadcast realtime update AFTER transaction commit
        self.event_bus.publish(
            event_type="BOOKING_CREATED",
            payload={
                "booking_id": result_dto["booking_id"],
                "slot_id": result_dto["slot_id"],
                "status": result_dto["status"],
                "expires_at": result_dto["expires_at"],
            },
            now_utc=now_dt,
        )
        return result_dto

    def cancel_booking(
        self,
        booking_id: str,
        requester_user_id: int,
        requester_role: str = UserRole.USER.value,
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Cancel a booking when still in 'Reserved' status and checkin has not started.
        Follows strict lock ordering: vehicles (1) -> parking_slots (2) -> bookings (3).
        """
        now_dt = now_utc or utc_now()

        def _tx(tx) -> Dict[str, Any]:
            # Lookup candidate metadata first before acquiring locks so we can lock in canonical order
            candidate = tx.bookings.get_by_id(booking_id)
            if candidate is None:
                raise ResourceNotFoundException(
                    f"Không tìm thấy đặt chỗ {booking_id}.",
                    reason_code="BOOKING_NOT_FOUND",
                )
            if requester_role != UserRole.ADMIN.value and int(candidate.user_id) != int(requester_user_id):
                raise AuthorizationException(
                    "Bạn không có quyền hủy đặt chỗ của người dùng khác.",
                    reason_code="FORBIDDEN_NOT_BOOKING_OWNER",
                )

            # LOCK 1: vehicles
            vehicle = tx.vehicles.lock_by_id_for_update(candidate.vehicle_id)
            # LOCK 2: parking_slots
            tx.slots.lock_by_id_for_update(candidate.slot_id)
            # LOCK 3: bookings
            booking = tx.bookings.lock_by_id_for_update(booking_id)
            if booking is None:
                raise ResourceNotFoundException("Không tìm thấy đặt chỗ.", reason_code="BOOKING_NOT_FOUND")

            if booking.status != BookingStatus.RESERVED or booking.checkin_event_id is not None:
                raise BookingConflictException(
                    f"Không thể hủy đặt chỗ khi đang ở trạng thái '{booking.status.value}' "
                    "(xe đang đối soát tại cổng hoặc đặt chỗ đã kết thúc).",
                    reason_code="BOOKING_CANNOT_BE_CANCELLED",
                    details={
                        "booking_id": booking.booking_id,
                        "current_status": booking.status.value,
                        "checkin_event_id": booking.checkin_event_id,
                    },
                )

            if booking.expires_at <= now_dt:
                raise BookingConflictException(
                    "Đặt chỗ đã quá thời hạn 60 phút, không thể hủy thủ công (hệ thống tự động chuyển Expired).",
                    reason_code="BOOKING_ALREADY_EXPIRED",
                    details={
                        "booking_id": booking.booking_id,
                        "expires_at": format_utc_iso(booking.expires_at),
                    },
                )

            tx.bookings.mark_cancelled(booking.booking_id, now_utc=now_dt)
            tx.slots.release_booking_if_matches(
                slot_id=booking.slot_id,
                booking_id=booking.booking_id,
                now_utc=now_dt,
            )

            tx.parking_logs.append(
                event_type=LogEventType.BOOKING_CANCELLED.value,
                reason_code="USER_CANCELLED_BOOKING" if requester_role == UserRole.USER.value else "ADMIN_CANCELLED_BOOKING",
                actor_user_id=requester_user_id,
                details={
                    "booking_id": booking.booking_id,
                    "slot_id": booking.slot_id,
                    "vehicle_id": booking.vehicle_id,
                },
                created_at=now_dt,
            )

            updated = tx.bookings.get_by_id(booking.booking_id)
            assert updated is not None
            if vehicle is not None:
                updated.plate_number = vehicle.plate_number
            return self._booking_to_dto(updated, now_dt)

        result_dto = self.uow.run_transactional(_tx)
        self.event_bus.publish(
            event_type="BOOKING_CANCELLED",
            payload={
                "booking_id": result_dto["booking_id"],
                "slot_id": result_dto["slot_id"],
                "status": result_dto["status"],
                "cancelled_at": result_dto["cancelled_at"],
            },
            now_utc=now_dt,
        )
        return result_dto

    def expire_overdue_bookings(self, now_utc: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Worker & service function to expire overdue 'Reserved' bookings:
        1. Query candidate overdue bookings outside lock.
        2. For each candidate, open a short transaction and lock in canonical order:
           vehicles (1) -> parking_slots (2) -> bookings (3) -> sessions (4)
        3. Re-verify booking is still 'Reserved', expires_at <= now_utc, checkin_event_id IS NULL,
           and no session has been created for this booking.
        4. Release parking_slots.active_booking_id = NULL ONLY if active_booking_id == booking_id.
        """
        now_dt = now_utc or utc_now()

        def _query_candidates(tx) -> List[Dict[str, Any]]:
            return tx.bookings.find_overdue_reserved_candidates(now_dt)

        candidates = self.uow.run_transactional(_query_candidates, readonly=True)
        expired_items: List[Dict[str, Any]] = []

        for cand in candidates:
            b_id = str(cand["booking_id"])
            v_id = int(cand["vehicle_id"])
            s_id = str(cand["slot_id"])

            def _expire_one(tx, booking_id=b_id, vehicle_id=v_id, slot_id=s_id) -> Optional[Dict[str, Any]]:
                # Mandatory lock order: vehicles (1) -> parking_slots (2) -> bookings (3) -> sessions (4)
                tx.vehicles.lock_by_id_for_update(vehicle_id)
                tx.slots.lock_by_id_for_update(slot_id)
                booking = tx.bookings.lock_by_id_for_update(booking_id)
                if booking is None:
                    return None

                # Protect bookings that have entered Checkin_pending / Checked_in right near expiry (T06)!
                if booking.status != BookingStatus.RESERVED:
                    return None
                if booking.expires_at > now_dt:
                    return None
                if booking.checkin_event_id is not None:
                    return None

                linked_session = tx.sessions.find_by_booking_id(booking_id)
                if linked_session is not None:
                    return None

                tx.bookings.mark_expired(booking_id)
                slot_released = tx.slots.release_booking_if_matches(
                    slot_id=booking.slot_id,
                    booking_id=booking_id,
                    now_utc=now_dt,
                )

                tx.parking_logs.append(
                    event_type=LogEventType.BOOKING_EXPIRED.value,
                    reason_code="BOOKING_TTL_60M_EXPIRED",
                    actor_user_id=None,
                    details={
                        "booking_id": booking_id,
                        "slot_id": booking.slot_id,
                        "vehicle_id": booking.vehicle_id,
                        "slot_released": slot_released,
                    },
                    created_at=now_dt,
                )

                updated = tx.bookings.get_by_id(booking_id)
                assert updated is not None
                return self._booking_to_dto(updated, now_dt)

            expired_dto = self.uow.run_transactional(_expire_one)
            if expired_dto is not None:
                expired_items.append(expired_dto)
                self.event_bus.publish(
                    event_type="BOOKING_EXPIRED",
                    payload={
                        "booking_id": expired_dto["booking_id"],
                        "slot_id": expired_dto["slot_id"],
                        "status": expired_dto["status"],
                    },
                    now_utc=now_dt,
                )

        return expired_items

    def get_current_booking(
        self,
        user_id: int,
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Return the user's current active booking + server_time so page reload (F5)
        computes remaining_seconds = expires_at - server_time accurately without resetting to 60m.
        """
        now_dt = now_utc or utc_now()

        def _tx(tx) -> Optional[Dict[str, Any]]:
            booking = tx.bookings.find_current_for_user(user_id)
            if booking is None:
                return None
            dto = self._booking_to_dto(booking, now_dt)
            linked_session = tx.sessions.find_by_booking_id(booking.booking_id)
            if linked_session is not None:
                dto["session_id"] = linked_session.session_id
                dto["session_status"] = linked_session.status.value
                dto["parking_status"] = linked_session.parking_status.value
                dto["entry_time"] = format_utc_iso(linked_session.entry_time)
                dto["entry_time_vn"] = format_vn_iso(linked_session.entry_time)
            else:
                dto["session_id"] = None
                dto["session_status"] = None
                dto["parking_status"] = None
                dto["entry_time"] = None
                dto["entry_time_vn"] = None
            return dto

        booking_dto = self.uow.run_transactional(_tx, readonly=True)
        return {
            "booking": booking_dto,
            "server_time": format_utc_iso(now_dt),
            "server_time_vn": format_vn_iso(now_dt),
        }

    def get_booking_detail(
        self,
        booking_id: str,
        requester_user_id: int,
        requester_role: str = UserRole.USER.value,
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Return booking detail; only booking owner or ADMIN is authorized."""
        now_dt = now_utc or utc_now()

        def _tx(tx) -> Dict[str, Any]:
            booking = tx.bookings.get_by_id(booking_id)
            if booking is None:
                raise ResourceNotFoundException("Không tìm thấy đặt chỗ.", reason_code="BOOKING_NOT_FOUND")
            if requester_role != UserRole.ADMIN.value and int(booking.user_id) != int(requester_user_id):
                raise AuthorizationException(
                    "Bạn không có quyền xem thông tin đặt chỗ của người dùng khác.",
                    reason_code="FORBIDDEN_NOT_BOOKING_OWNER",
                )
            return self._booking_to_dto(booking, now_dt)

        return self.uow.run_transactional(_tx, readonly=True)

    def get_user_history(
        self,
        user_id: int,
        booking_status: Optional[str] = None,
        session_status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Return personal booking history and parking session history for authenticated user_id."""
        now_dt = now_utc or utc_now()

        def _tx(tx) -> Dict[str, Any]:
            bookings = tx.bookings.list_by_user(
                user_id=user_id,
                status_filter=booking_status,
                limit=limit,
                offset=offset,
            )
            sessions = tx.sessions.list_by_user(
                user_id=user_id,
                status_filter=session_status,
                limit=limit,
                offset=offset,
            )
            return {
                "bookings": [self._booking_to_dto(b, now_dt) for b in bookings],
                "sessions": [
                    {
                        "session_id": s.session_id,
                        "plate_number": s.plate_number,
                        "plate_display": PlateNormalizer.format_display(s.plate_number),
                        "booking_id": s.booking_id,
                        "assigned_slot_id": s.assigned_slot_id,
                        "status": s.status.value,
                        "parking_status": s.parking_status.value,
                        "ocr_confidence": s.ocr_confidence,
                        "entry_time": format_utc_iso(s.entry_time),
                        "entry_time_vn": format_vn_iso(s.entry_time),
                        "exit_time": format_utc_iso(s.exit_time),
                        "exit_time_vn": format_vn_iso(s.exit_time),
                        "created_at": format_utc_iso(s.created_at),
                        "created_at_vn": format_vn_iso(s.created_at),
                    }
                    for s in sessions
                ],
                "limit": limit,
                "offset": offset,
                "server_time": format_utc_iso(now_dt),
                "server_time_vn": format_vn_iso(now_dt),
            }

        return self.uow.run_transactional(_tx, readonly=True)

    @staticmethod
    def _booking_to_dto(booking: Booking, now_dt: datetime) -> Dict[str, Any]:
        rem_sec = 0
        if booking.status == BookingStatus.RESERVED and booking.expires_at > now_dt:
            rem_sec = max(0, int((booking.expires_at - now_dt).total_seconds()))
        can_cancel = (
            booking.status == BookingStatus.RESERVED
            and booking.checkin_event_id is None
            and rem_sec > 0
        )
        return {
            "booking_id": booking.booking_id,
            "user_id": booking.user_id,
            "vehicle_id": booking.vehicle_id,
            "plate_number": booking.plate_number,
            "plate_display": PlateNormalizer.format_display(booking.plate_number) if booking.plate_number else None,
            "slot_id": booking.slot_id,
            "status": booking.status.value,
            "created_at": format_utc_iso(booking.created_at),
            "created_at_vn": format_vn_iso(booking.created_at),
            "expires_at": format_utc_iso(booking.expires_at),
            "expires_at_vn": format_vn_iso(booking.expires_at),
            "checkin_started_at": format_utc_iso(booking.checkin_started_at),
            "checked_in_at": format_utc_iso(booking.checked_in_at),
            "completed_at": format_utc_iso(booking.completed_at),
            "cancelled_at": format_utc_iso(booking.cancelled_at),
            "checkin_event_id": booking.checkin_event_id,
            "remaining_seconds": rem_sec,
            "can_cancel": can_cancel,
            "server_time": format_utc_iso(now_dt),
            "server_time_vn": format_vn_iso(now_dt),
        }
