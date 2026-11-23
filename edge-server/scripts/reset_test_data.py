"""Preview/reset parking test transactions while preserving accounts and configuration.

The backend must be stopped and both ESP boards powered off before --apply.
Use scripts/reset_test_data.ps1 to stop/restart the local backend automatically.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import socket
import sys

EDGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EDGE / "src"))

from smart_parking.ai.plate.normalizer import PlateNormalizer
from smart_parking.ai.plate.validator import PlateValidator
from smart_parking.config.settings import Settings
from smart_parking.infrastructure.database.mysql_db import MySQLDatabase, to_db_utc, utc_now
from smart_parking.infrastructure.database.unit_of_work import UnitOfWork

DELETE_TABLES = ("parking_logs", "gate_events", "session_face_templates", "sessions", "bookings")
KEEP_TABLES = ("users", "vehicles", "user_face_templates", "parking_slots")


def _counts(cursor):
    result = {}
    for table in DELETE_TABLES + KEEP_TABLES:
        cursor.execute(f"SELECT COUNT(*) AS total FROM {table}")
        result[table] = int(cursor.fetchone()["total"])
    return result


def _vehicle_change(cursor, username, plate, *, lock=False):
    if plate is None:
        return None
    normalized = PlateNormalizer.normalize(plate)
    if not PlateValidator.is_valid_vietnamese_plate(normalized):
        raise ValueError("Invalid normalized demo plate")
    suffix = " FOR UPDATE" if lock else ""
    cursor.execute(
        "SELECT v.vehicle_id,v.plate_number FROM vehicles v JOIN users u ON u.user_id=v.user_id "
        "WHERE u.username=%s AND u.role='user' AND v.status='Active'" + suffix, (username,))
    rows = cursor.fetchall()
    if len(rows) != 1:
        raise ValueError("Demo USER must have exactly one active vehicle; no vehicle was guessed")
    cursor.execute("SELECT vehicle_id FROM vehicles WHERE plate_number=%s" + suffix, (normalized,))
    collision = cursor.fetchone()
    if collision and collision["vehicle_id"] != rows[0]["vehicle_id"]:
        raise ValueError("New plate already belongs to another vehicle")
    return {"username": username, "vehicle_id": rows[0]["vehicle_id"],
            "old_plate": rows[0]["plate_number"], "new_plate": normalized}


def preview_reset(uow, *, demo_username=None, demo_plate=None):
    def read(tx):
        counts = _counts(tx.cursor)
        return {"delete": {name: counts[name] for name in DELETE_TABLES},
                "keep": {name: counts[name] for name in KEEP_TABLES},
                "slots_after_reset": "Unknown; waiting for fresh IR data",
                "vehicle_change": _vehicle_change(tx.cursor, demo_username, demo_plate)}
    return uow.run_transactional(read, readonly=True)


def reset_test_data(uow, *, demo_username=None, demo_plate=None):
    """One transaction, foreign keys enabled, no TRUNCATE/DROP or account reseeding."""
    def reset(tx):
        cursor = tx.cursor
        change = _vehicle_change(cursor, demo_username, demo_plate, lock=True)
        before = _counts(cursor)
        if change:
            cursor.execute("UPDATE vehicles SET plate_number=%s,updated_at=%s WHERE vehicle_id=%s",
                           (change["new_plate"], to_db_utc(utc_now()), change["vehicle_id"]))
        cursor.execute("UPDATE parking_slots SET active_booking_id=NULL,reserved_session_id=NULL,"
                       "physical_status='Unknown',last_boot_id=NULL,last_sequence=NULL,last_seen_at=NULL,updated_at=%s",
                       (to_db_utc(utc_now()),))
        # Break circular references before deleting their targets.
        cursor.execute("UPDATE bookings SET checkin_event_id=NULL")
        for table in DELETE_TABLES:
            cursor.execute(f"DELETE FROM {table}")
        after = _counts(cursor)
        if any(after[table] for table in DELETE_TABLES):
            raise RuntimeError("Reset did not empty all transaction tables")
        if any(after[table] != before[table] for table in KEEP_TABLES):
            raise RuntimeError("Preserved table row count changed; rolling back")
        return {"deleted": {name: before[name] for name in DELETE_TABLES},
                "preserved": {name: after[name] for name in KEEP_TABLES}, "vehicle_change": change}
    return uow.run_transactional(reset)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply the reset; default is preview only")
    parser.add_argument("--database", help="Must exactly match MYSQL_DATABASE when applying")
    parser.add_argument("--demo-plate", help="Also update the existing demo USER's single active vehicle")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    cfg = Settings()
    if args.apply:
        if args.database != cfg.mysql_database:
            parser.error("--database must exactly match the database in the local settings")
        with socket.socket() as probe:
            probe.settimeout(.5)
            if probe.connect_ex(("127.0.0.1", cfg.http_port)) == 0:
                parser.error("Stop the backend before applying; use scripts/reset_test_data.ps1")
    uow = UnitOfWork(MySQLDatabase(cfg))
    fn = reset_test_data if args.apply else preview_reset
    result = fn(uow, demo_username=cfg.demo_user_username, demo_plate=args.demo_plate)
    result.update(database=cfg.mysql_database, http_port=cfg.http_port, applied=args.apply)
    print(json.dumps(result, ensure_ascii=True, indent=None if args.json else 2))


if __name__ == "__main__":
    main()
