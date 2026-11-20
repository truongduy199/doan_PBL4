"""Review Repository for Admin Manual Review queries (`gate_events` & `sessions`)."""
from __future__ import annotations

from typing import Any, Dict, List

from smart_parking.infrastructure.database.mysql_db import DBCursorProtocol, LockOrderTracker


class ReviewRepository:
    """Queries gate events requiring manual review and sessions with parking anomalies."""

    def __init__(self, cursor: DBCursorProtocol, lock_tracker: LockOrderTracker) -> None:
        self._cursor = cursor
        self._locks = lock_tracker

    def list_reviews(self, include_resolved: bool = False) -> List[Dict[str, Any]]:
        if include_resolved:
            self._cursor.execute(
                "SELECT ge.*, s.plate_number, s.assigned_slot_id, s.status AS session_status, "
                "s.parking_status, b.slot_id AS booking_slot_id, u.username AS reviewer_username "
                "FROM gate_events ge "
                "LEFT JOIN sessions s ON s.session_id = ge.session_id "
                "LEFT JOIN bookings b ON b.booking_id = ge.booking_id "
                "LEFT JOIN users u ON u.user_id = ge.reviewer_id "
                "WHERE ge.decision = 'Review_required' OR ge.reviewer_id IS NOT NULL "
                "ORDER BY ge.created_at DESC LIMIT 100"
            )
        else:
            self._cursor.execute(
                "SELECT ge.*, s.plate_number, s.assigned_slot_id, s.status AS session_status, "
                "s.parking_status, b.slot_id AS booking_slot_id, u.username AS reviewer_username "
                "FROM gate_events ge "
                "LEFT JOIN sessions s ON s.session_id = ge.session_id "
                "LEFT JOIN bookings b ON b.booking_id = ge.booking_id "
                "LEFT JOIN users u ON u.user_id = ge.reviewer_id "
                "WHERE ge.decision = 'Review_required' "
                "ORDER BY ge.created_at DESC LIMIT 100"
            )
        gate_reviews = list(self._cursor.fetchall())

        # Also query sessions with parking anomalies (Parking_review_required or Parking_timeout)
        self._cursor.execute(
            "SELECT s.session_id, s.plate_number, s.assigned_slot_id, s.status AS session_status, "
            "s.parking_status, s.entry_time, s.created_at, s.updated_at "
            "FROM sessions s "
            "WHERE s.status IN ('Entry_pending', 'Active', 'Exit_pending') "
            "AND s.parking_status IN ('Parking_review_required', 'Parking_timeout') "
            "ORDER BY s.updated_at DESC"
        )
        parking_anomalies = list(self._cursor.fetchall())

        results: List[Dict[str, Any]] = []
        for row in gate_reviews:
            results.append({
                "review_type": "GATE_EVENT",
                "event_id": row["event_id"],
                "gate_id": row["gate_id"],
                "device_id": row["device_id"],
                "session_id": row.get("session_id"),
                "booking_id": row.get("booking_id"),
                "plate_number": row.get("plate_number"),
                "slot_id": row.get("assigned_slot_id") or row.get("booking_slot_id"),
                "decision": row["decision"],
                "passage_status": row["passage_status"],
                "reason_code": row.get("reason_code"),
                "liveness_status": row.get("liveness_status"),
                "liveness_score": row.get("liveness_score"),
                "reviewer_id": row.get("reviewer_id"),
                "reviewer_username": row.get("reviewer_username"),
                "review_reason": row.get("review_reason"),
                "created_at": row.get("created_at"),
                "decided_at": row.get("decided_at"),
            })

        for srow in parking_anomalies:
            results.append({
                "review_type": "PARKING_ANOMALY",
                "event_id": f"PARK-{srow['session_id']}",
                "gate_id": "IN",
                "device_id": "IR_ARRAY",
                "session_id": srow["session_id"],
                "booking_id": None,
                "plate_number": srow["plate_number"],
                "slot_id": srow["assigned_slot_id"],
                "decision": "Review_required",
                "passage_status": "Confirmed",
                "reason_code": srow["parking_status"],
                "liveness_status": None,
                "liveness_score": None,
                "reviewer_id": None,
                "reviewer_username": None,
                "review_reason": None,
                "created_at": srow.get("updated_at") or srow.get("created_at"),
                "decided_at": None,
            })

        return results
