"""Bootstrap: Wire configurations, MySQL unit of work, application services, and FastAPI app."""
from __future__ import annotations

from typing import Any, Dict, Optional

from smart_parking.config.settings import Settings, get_settings
from smart_parking.infrastructure.database.mysql_db import MySQLDatabase
from smart_parking.interfaces.http.app import create_app
from smart_parking.interfaces.http.dependencies import AppContainer, build_container
from smart_parking.workers.retention_worker import BookingExpiryAndRetentionWorker


def bootstrap_system(
    settings: Optional[Settings] = None,
    db: Optional[MySQLDatabase] = None,
) -> Dict[str, Any]:
    """Khởi tạo và kết nối toàn bộ thành phần hệ thống theo kiến trúc MySQL + FastAPI."""
    cfg = settings or get_settings()
    container: AppContainer = build_container(settings=cfg, db=db)
    fastapi_app = create_app(container=container)
    expiry_worker = BookingExpiryAndRetentionWorker(
        booking_service=container.booking_service,
        retention_service=container.retention_service,
        interval_seconds=cfg.expiry_worker_interval_seconds,
    )
    return {
        "settings": cfg,
        "container": container,
        "app": fastapi_app,
        "expiry_worker": expiry_worker,
    }
