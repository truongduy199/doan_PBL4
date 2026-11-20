"""Script xóa các bản ghi session_face_templates đã hết hạn retention trong MySQL."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_EDGE_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = _EDGE_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from smart_parking.application.services.retention_service import RetentionService
from smart_parking.config.settings import get_settings
from smart_parking.infrastructure.database.mysql_db import MySQLDatabase
from smart_parking.infrastructure.database.unit_of_work import UnitOfWork


def main() -> None:
    settings = get_settings()
    db = MySQLDatabase(settings)
    uow = UnitOfWork(db)
    service = RetentionService(uow=uow)
    result = service.purge_expired_session_templates()
    print("[OK] Retention purge result:")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
