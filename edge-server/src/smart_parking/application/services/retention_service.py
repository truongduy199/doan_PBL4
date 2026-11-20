"""Retention Service: Purges expired `session_face_templates` for Closed/Cancelled sessions."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from smart_parking.application.services.event_service import RealtimeEventBus
from smart_parking.domain.enums import LogEventType
from smart_parking.infrastructure.database.mysql_db import format_utc_iso, utc_now
from smart_parking.infrastructure.database.unit_of_work import UnitOfWork


class RetentionService:
    """
    Purges expired session face templates according to data retention policy:
    - Only deletes `session_face_templates` whose linked session is `'Closed'` or `'Cancelled'`
      and `expires_at <= now_utc`.
    - Never deletes templates of live sessions (`'Entry_pending'`, `'Active'`, `'Exit_pending'`).
    - Never deletes `user_face_templates`.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        event_bus: Optional[RealtimeEventBus] = None,
    ) -> None:
        self.uow = uow
        self.event_bus = event_bus or RealtimeEventBus()

    def purge_expired_session_templates(
        self,
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        now_dt = now_utc or utc_now()

        def _tx(tx) -> int:
            deleted_count = tx.face_templates.purge_expired_session_templates(now_dt)
            if deleted_count > 0:
                tx.parking_logs.append(
                    event_type=LogEventType.RETENTION_PURGE.value,
                    reason_code="EXPIRED_SESSION_FACE_TEMPLATES_PURGED",
                    details={"purged_count": deleted_count},
                    created_at=now_dt,
                )
            return deleted_count

        purged = self.uow.run_transactional(_tx)
        result = {
            "purged_count": purged,
            "executed_at": format_utc_iso(now_dt),
        }
        if purged > 0:
            self.event_bus.publish("RETENTION_PURGE_COMPLETED", result, now_utc=now_dt)
        return result
