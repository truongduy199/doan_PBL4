"""Health Route (/health and /api/health)."""
from __future__ import annotations

from typing import Any, Dict

from smart_parking.infrastructure.database.mysql_db import format_utc_iso, utc_now
from smart_parking.interfaces.http._compat import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
def get_health() -> Dict[str, Any]:
    return {"status": "ok", "server_time": format_utc_iso(utc_now())}


@router.get("/api/health")
def get_api_health() -> Dict[str, Any]:
    return {"status": "ok", "database_engine": "MySQL/InnoDB", "server_time": format_utc_iso(utc_now())}
