"""Admin Query & Session Service for Admin Dashboard coordination."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from smart_parking.ai.plate.normalizer import PlateNormalizer
from smart_parking.infrastructure.database.mysql_db import (
    format_utc_iso,
    format_vn_iso,
    from_db_utc,
    utc_now,
)
from smart_parking.infrastructure.database.unit_of_work import UnitOfWork


class AdminQueryService:
    """Provides admin query views for sessions, bookings, manual reviews, and audit logs."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def list_sessions(
        self,
        status_filter: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        now_dt = now_utc or utc_now()

        def _tx(tx) -> List[Dict[str, Any]]:
            rows = tx.sessions.list_all_admin(status_filter=status_filter, limit=limit, offset=offset)
            items: List[Dict[str, Any]] = []
            for r in rows:
                b_exp = from_db_utc(r.get("booking_expires_at"))
                rem_sec = max(0, int((b_exp - now_dt).total_seconds())) if b_exp and b_exp > now_dt else 0
                items.append({
                    "session_id": r["session_id"],
                    "plate_number": r["plate_number"],
                    "plate_display": PlateNormalizer.format_display(r["plate_number"]),
                    "user_id": r.get("user_id"),
                    "username": r.get("username"),
                    "display_name": r.get("display_name"),
                    "vehicle_id": r.get("vehicle_id"),
                    "booking_id": r.get("booking_id"),
                    "booking_status": r.get("booking_status"),
                    "booking_expires_at": format_utc_iso(b_exp),
                    "booking_expires_at_vn": format_vn_iso(b_exp),
                    "booking_remaining_seconds": rem_sec,
                    "assigned_slot_id": r["assigned_slot_id"],
                    "status": r["status"],
                    "parking_status": r["parking_status"],
                    "ocr_confidence": r.get("ocr_confidence"),
                    "entry_time": format_utc_iso(r.get("entry_time")),
                    "entry_time_vn": format_vn_iso(r.get("entry_time")),
                    "exit_time": format_utc_iso(r.get("exit_time")),
                    "exit_time_vn": format_vn_iso(r.get("exit_time")),
                    "created_at": format_utc_iso(r.get("created_at")),
                    "created_at_vn": format_vn_iso(r.get("created_at")),
                    "updated_at": format_utc_iso(r.get("updated_at")),
                })
            return items

        sessions = self.uow.run_transactional(_tx, readonly=True)
        return {
            "sessions": sessions,
            "count": len(sessions),
            "server_time": format_utc_iso(now_dt),
            "server_time_vn": format_vn_iso(now_dt),
        }

    def list_bookings(
        self,
        status_filter: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        now_dt = now_utc or utc_now()

        def _tx(tx) -> List[Dict[str, Any]]:
            rows = tx.bookings.list_all_admin(status_filter=status_filter, limit=limit, offset=offset)
            items: List[Dict[str, Any]] = []
            for r in rows:
                exp = from_db_utc(r["expires_at"])
                rem_sec = 0
                if r["status"] == "Reserved" and exp and exp > now_dt:
                    rem_sec = max(0, int((exp - now_dt).total_seconds()))
                plate = r.get("plate_number")
                items.append({
                    "booking_id": r["booking_id"],
                    "user_id": r["user_id"],
                    "username": r.get("username"),
                    "display_name": r.get("display_name"),
                    "vehicle_id": r["vehicle_id"],
                    "plate_number": plate,
                    "plate_display": PlateNormalizer.format_display(plate) if plate else None,
                    "slot_id": r["slot_id"],
                    "status": r["status"],
                    "created_at": format_utc_iso(r.get("created_at")),
                    "created_at_vn": format_vn_iso(r.get("created_at")),
                    "expires_at": format_utc_iso(exp),
                    "expires_at_vn": format_vn_iso(exp),
                    "remaining_seconds": rem_sec,
                    "checkin_started_at": format_utc_iso(r.get("checkin_started_at")),
                    "checked_in_at": format_utc_iso(r.get("checked_in_at")),
                    "completed_at": format_utc_iso(r.get("completed_at")),
                    "cancelled_at": format_utc_iso(r.get("cancelled_at")),
                    "checkin_event_id": r.get("checkin_event_id"),
                })
            return items

        bookings = self.uow.run_transactional(_tx, readonly=True)
        return {
            "bookings": bookings,
            "count": len(bookings),
            "server_time": format_utc_iso(now_dt),
            "server_time_vn": format_vn_iso(now_dt),
        }

    def list_reviews(
        self,
        include_resolved: bool = False,
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        now_dt = now_utc or utc_now()

        def _tx(tx) -> List[Dict[str, Any]]:
            rows = tx.reviews.list_reviews(include_resolved=include_resolved)
            for r in rows:
                plate = r.get("plate_number")
                r["plate_display"] = PlateNormalizer.format_display(plate) if plate else None
                r["created_at"] = format_utc_iso(r.get("created_at"))
                r["created_at_vn"] = format_vn_iso(r.get("created_at"))
                r["decided_at"] = format_utc_iso(r.get("decided_at"))
            return rows

        reviews = self.uow.run_transactional(_tx, readonly=True)
        return {
            "reviews": reviews,
            "count": len(reviews),
            "server_time": format_utc_iso(now_dt),
            "server_time_vn": format_vn_iso(now_dt),
        }

    def list_audit_logs(
        self,
        limit: int = 50,
        session_id: Optional[str] = None,
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        now_dt = now_utc or utc_now()

        def _tx(tx) -> List[Dict[str, Any]]:
            logs = tx.parking_logs.list_recent(limit=limit, session_id=session_id)
            return [
                {
                    "log_id": lg.log_id,
                    "event_id": lg.event_id,
                    "session_id": lg.session_id,
                    "actor_user_id": lg.actor_user_id,
                    "event_type": lg.event_type,
                    "reason_code": lg.reason_code,
                    "details": lg.details,
                    "created_at": format_utc_iso(lg.created_at),
                    "created_at_vn": format_vn_iso(lg.created_at),
                }
                for lg in logs
            ]

        items = self.uow.run_transactional(_tx, readonly=True)
        return {
            "logs": items,
            "count": len(items),
            "server_time": format_utc_iso(now_dt),
            "server_time_vn": format_vn_iso(now_dt),
        }


# Backwards-compatible alias
SessionService = AdminQueryService
