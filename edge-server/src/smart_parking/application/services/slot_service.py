"""Slot Service: Computes 4-slot availability, composite UI state, and role-based privacy masking."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from smart_parking.ai.plate.normalizer import PlateNormalizer
from smart_parking.config.settings import Settings, get_settings
from smart_parking.domain.enums import DisplaySlotStatus, PhysicalSlotStatus, UserRole
from smart_parking.infrastructure.database.mysql_db import format_utc_iso, format_vn_iso, utc_now
from smart_parking.infrastructure.database.unit_of_work import UnitOfWork


class SlotService:
    """Provides 4-slot status views with strict separation of physical IR state vs reservation right."""

    def __init__(self, uow: UnitOfWork, settings: Optional[Settings] = None) -> None:
        self.uow = uow
        self.settings = settings or get_settings()

    def get_slots_view(
        self,
        viewer_user_id: Optional[int],
        viewer_role: str = UserRole.USER.value,
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Return the 4 parking slots (A1, A2, B1, B2) with role-based data protection."""
        now_dt = now_utc or utc_now()
        stale_sec = self.settings.slot_stale_seconds
        is_admin = viewer_role == UserRole.ADMIN.value

        def _tx(tx) -> List[Dict[str, Any]]:
            slots = tx.slots.get_all_slots()
            items: List[Dict[str, Any]] = []
            for slot in slots:
                booking = (
                    tx.bookings.get_by_id(slot.active_booking_id)
                    if slot.active_booking_id
                    else None
                )
                session = (
                    tx.sessions.get_by_id(slot.reserved_session_id)
                    if slot.reserved_session_id
                    else None
                )
                booking_user = (
                    tx.users.get_by_id(booking.user_id)
                    if (booking and is_admin)
                    else None
                )

                fresh = slot.is_sensor_fresh(now_dt, stale_sec)
                available = slot.is_available(now_dt, stale_sec)
                display_enum, label_vi = slot.compute_display_status(now_dt, stale_sec)

                is_my_booking = bool(
                    booking is not None
                    and viewer_user_id is not None
                    and int(booking.user_id) == int(viewer_user_id)
                )
                is_my_session = bool(
                    session is not None
                    and viewer_user_id is not None
                    and session.user_id is not None
                    and int(session.user_id) == int(viewer_user_id)
                )

                # Adjust Vietnamese label for USER viewing someone else's reserved slot
                if (
                    not is_admin
                    and display_enum == DisplaySlotStatus.RESERVED
                    and not is_my_booking
                ):
                    label_vi = "Đã được đặt"

                remaining_seconds: Optional[int] = None
                if booking is not None and booking.expires_at is not None:
                    diff = int((booking.expires_at - now_dt).total_seconds())
                    remaining_seconds = max(0, diff)

                # Role-based masking: USER only sees booking/plate details for their own booking/session
                can_see_details = is_admin or is_my_booking or is_my_session
                raw_plate: Optional[str] = None
                if can_see_details:
                    if session is not None and session.plate_number:
                        raw_plate = session.plate_number
                    elif booking is not None and booking.plate_number:
                        raw_plate = booking.plate_number

                slot_dto: Dict[str, Any] = {
                    "slot_id": slot.slot_id,
                    "sensor_id": slot.sensor_id,
                    "physical_status": slot.physical_status.value,
                    "display_status": display_enum.value,
                    "label_vi": label_vi,
                    "is_available": available,
                    "is_bookable": available,
                    "sensor_fresh": fresh,
                    "is_my_booking": is_my_booking,
                    "is_my_session": is_my_session,
                    "booking_id": booking.booking_id if (booking and can_see_details) else None,
                    "booking_status": booking.status.value if (booking and can_see_details) else None,
                    "expires_at": format_utc_iso(booking.expires_at) if (booking and can_see_details) else None,
                    "expires_at_vn": format_vn_iso(booking.expires_at) if (booking and can_see_details) else None,
                    "remaining_seconds": remaining_seconds if (booking and can_see_details) else None,
                    "plate_number": raw_plate,
                    "plate_display": PlateNormalizer.format_display(raw_plate) if raw_plate else None,
                    "updated_at": format_utc_iso(slot.updated_at),
                    "updated_at_vn": format_vn_iso(slot.updated_at),
                    "last_seen_at": format_utc_iso(slot.last_seen_at),
                    "last_seen_at_vn": format_vn_iso(slot.last_seen_at),
                }

                if is_admin:
                    slot_dto.update({
                        "active_booking_id": slot.active_booking_id,
                        "reserved_session_id": slot.reserved_session_id,
                        "session_status": session.status.value if session else None,
                        "parking_status": session.parking_status.value if session else None,
                        "entry_time": format_utc_iso(session.entry_time) if session else None,
                        "entry_time_vn": format_vn_iso(session.entry_time) if session else None,
                        "booked_by_user_id": booking.user_id if booking else None,
                        "booked_by_username": booking_user.username if booking_user else None,
                        "booked_by_display_name": booking_user.display_name if booking_user else None,
                        "last_boot_id": slot.last_boot_id,
                        "last_sequence": slot.last_sequence,
                    })

                items.append(slot_dto)
            return items

        slot_items = self.uow.run_transactional(_tx, readonly=True)
        available_count = sum(1 for s in slot_items if s["is_available"])
        return {
            "slots": slot_items,
            "available_count": available_count,
            "total_count": len(slot_items),
            "slot_stale_seconds": stale_sec,
            "server_time": format_utc_iso(now_dt),
            "server_time_vn": format_vn_iso(now_dt),
        }

    def get_admin_devices_health(self, now_utc: Optional[datetime] = None) -> Dict[str, Any]:
        """Return sensor freshness, boot_id, and sequence status for the 4 IR slot sensors."""
        now_dt = now_utc or utc_now()
        stale_sec = self.settings.slot_stale_seconds

        def _tx(tx) -> List[Dict[str, Any]]:
            slots = tx.slots.get_all_slots()
            devices: List[Dict[str, Any]] = []
            for s in slots:
                fresh = s.is_sensor_fresh(now_dt, stale_sec)
                age_sec: Optional[float] = None
                if s.last_seen_at is not None:
                    age_sec = round((now_dt - s.last_seen_at).total_seconds(), 3)
                devices.append({
                    "slot_id": s.slot_id,
                    "sensor_id": s.sensor_id,
                    "physical_status": s.physical_status.value,
                    "is_fresh": fresh,
                    "is_fault": s.physical_status == PhysicalSlotStatus.FAULT,
                    "age_seconds": age_sec,
                    "stale_threshold_seconds": stale_sec,
                    "last_boot_id": s.last_boot_id,
                    "last_sequence": s.last_sequence,
                    "last_seen_at": format_utc_iso(s.last_seen_at),
                    "last_seen_at_vn": format_vn_iso(s.last_seen_at),
                    "updated_at": format_utc_iso(s.updated_at),
                })
            return devices

        sensor_list = self.uow.run_transactional(_tx, readonly=True)
        all_fresh = all(d["is_fresh"] and not d["is_fault"] for d in sensor_list)
        return {
            "overall_status": "HEALTHY" if all_fresh else "DEGRADED_OR_STALE",
            "slot_stale_seconds": stale_sec,
            "sensors": sensor_list,
            "server_time": format_utc_iso(now_dt),
            "server_time_vn": format_vn_iso(now_dt),
        }
