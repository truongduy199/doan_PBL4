"""Maintenance reset must preserve identities and roll back the entire operation on failure."""
import sys
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

EDGE = Path(__file__).resolve().parents[1]
for folder in (EDGE / "src", EDGE / "scripts", EDGE / "tests"):
    sys.path.insert(0, str(folder))
from reset_test_data import KEEP_TABLES, DELETE_TABLES, preview_reset, reset_test_data
from smart_parking.ai.plate.normalizer import PlateNormalizer
from smart_parking.ai.plate.validator import PlateValidator


@pytest.fixture
def runtime():
    from test_gate_runtime import GateRuntimeTests
    instance = GateRuntimeTests()
    instance.setUp()
    instance.detect("reset-entry")
    instance.decide("reset-entry")

    def add_booking(tx):
        slot = next(x for x in ("A1", "A2", "B1", "B2")
                    if x != instance.wf._turns["reset-entry"].last_decision["assigned_slot_id"])
        demo = instance.seed["demo_user"]
        tx.cursor.execute("INSERT INTO bookings (booking_id,user_id,vehicle_id,slot_id,status,created_at,expires_at,checkin_event_id) "
                          "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                          ("reset-booking", demo["user_id"], demo["vehicle_id"], slot, "Reserved", instance.now,
                           instance.now + timedelta(hours=1), "reset-entry"))
        tx.cursor.execute("UPDATE parking_slots SET active_booking_id=%s WHERE slot_id=%s", ("reset-booking", slot))
    instance.c.uow.run_transactional(add_booking)
    yield instance
    instance.tearDown()


def snapshot(runtime):
    def read(tx):
        data = {}
        for table in KEEP_TABLES + DELETE_TABLES:
            tx.cursor.execute(f"SELECT * FROM {table}")
            data[table] = tx.cursor.fetchall()
        return data
    return runtime.c.uow.run_transactional(read, readonly=True)


def test_reset_clears_transactions_preserves_credentials_and_templates(runtime):
    before = snapshot(runtime)
    result = reset_test_data(runtime.c.uow, demo_username=runtime.settings.demo_user_username, demo_plate="85-H6 503.46")
    after = snapshot(runtime)
    assert all(not after[name] for name in DELETE_TABLES)
    assert result["deleted"]["sessions"] == 1
    assert result["deleted"]["session_face_templates"] == 1
    assert before["users"] == after["users"]
    assert before["user_face_templates"] == after["user_face_templates"]
    assert len(before["vehicles"]) == len(after["vehicles"])
    target = next(x for x in after["vehicles"] if x["vehicle_id"] == runtime.seed["demo_user"]["vehicle_id"])
    assert target["plate_number"] == "85H650346"
    assert sorted((x["slot_id"], x["sensor_id"]) for x in before["parking_slots"]) == sorted((x["slot_id"], x["sensor_id"]) for x in after["parking_slots"])
    for slot in after["parking_slots"]:
        assert slot["physical_status"] == "Unknown"
        assert all(slot[key] is None for key in ("active_booking_id", "reserved_session_id", "last_boot_id", "last_sequence", "last_seen_at"))
    assert all(value == 0 for value in reset_test_data(runtime.c.uow)["deleted"].values())


def test_preview_changes_nothing(runtime):
    before = snapshot(runtime)
    plan = preview_reset(runtime.c.uow, demo_username=runtime.settings.demo_user_username, demo_plate="85H650346")
    assert plan["vehicle_change"]["new_plate"] == "85H650346"
    assert plan["delete"]["sessions"] == 1
    assert before == snapshot(runtime)


def test_failed_delete_rolls_back_plate_links_and_all_deleted_rows(runtime):
    from fakes.fake_mysql_db import _CompatCursor
    before = snapshot(runtime)
    execute = _CompatCursor.execute
    def fail_on_sessions(self, sql, params=()):
        if sql == "DELETE FROM sessions":
            raise RuntimeError("Injected write failure")
        return execute(self, sql, params)
    with patch.object(_CompatCursor, "execute", fail_on_sessions):
        with pytest.raises(RuntimeError):
            reset_test_data(runtime.c.uow, demo_username=runtime.settings.demo_user_username, demo_plate="85H650346")
    assert before == snapshot(runtime)


def test_wrong_user_cannot_delete_data(runtime):
    before = snapshot(runtime)
    with pytest.raises(ValueError):
        reset_test_data(runtime.c.uow, demo_username=runtime.settings.demo_admin_username, demo_plate="85H650346")
    assert before == snapshot(runtime)


@pytest.mark.parametrize("ambiguous", [False, True])
def test_plate_collision_or_multiple_vehicles_cannot_partially_reset(runtime, ambiguous):
    data = snapshot(runtime)
    demo_id = runtime.seed["demo_user"]["user_id"]
    other = next(x for x in data["vehicles"] if x["user_id"] != demo_id)
    if ambiguous:
        runtime.c.uow.run_transactional(lambda tx: tx.cursor.execute(
            "UPDATE vehicles SET user_id=%s WHERE vehicle_id=%s", (demo_id, other["vehicle_id"])))
    before = snapshot(runtime)
    with pytest.raises(ValueError):
        reset_test_data(runtime.c.uow, demo_username=runtime.settings.demo_user_username,
                        demo_plate="85H650346" if ambiguous else other["plate_number"])
    assert before == snapshot(runtime)


def test_normalization_preserves_series_letters_and_digits():
    for text in ("85H650346", "85-H6 503.46", "85h6-503.46"):
        plate = PlateNormalizer.normalize(text)
        assert plate == "85H650346"
        assert PlateValidator.is_valid_vietnamese_plate(plate)
    assert PlateNormalizer.format_display("85H650346") == "85H6-503.46"
    assert PlateValidator.is_valid_vietnamese_plate("37AF67769")
    assert not PlateValidator.is_valid_vietnamese_plate("85650346")
