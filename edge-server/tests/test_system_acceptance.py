"""
System acceptance tests for PBL4 Smart Parking IoT (MySQL/InnoDB + FastAPI).
Covers T01, T02, T03, T04, T05, T06, T07, T08, T13, T15, T19, T20, VII.4 RBAC, Lock Ordering, and Cipher.
"""
from __future__ import annotations

import sys
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np

_TESTS_DIR = Path(__file__).resolve().parent
_EDGE_ROOT = _TESTS_DIR.parent
_SRC_DIR = _EDGE_ROOT / "src"
for _p in (_TESTS_DIR, _SRC_DIR, _EDGE_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from fakes.fake_mysql_db import SandboxMySQLTestDatabase
from scripts.init_database import init_mysql_database
from scripts.seed_demo_data import make_deterministic_l2_vector, seed_demo_data
from smart_parking.config.settings import Settings
from smart_parking.domain.enums import (
    BookingStatus,
    LivenessStatus,
    ParkingStatus,
    SessionStatus,
)
from smart_parking.domain.exceptions import (
    BookingConflictException,
    SlotNotAvailableException,
)
from smart_parking.infrastructure.database.event_repository import sanitize_log_details
from smart_parking.infrastructure.database.mysql_db import (
    LockOrderTracker,
    LockOrderViolationError,
    MySQLDatabase,
    utc_now,
)
from smart_parking.infrastructure.database.unit_of_work import UnitOfWork
from smart_parking.infrastructure.security.embedding_cipher import EmbeddingCipher
from smart_parking.interfaces.http.app import LocalTestClient, create_app
from smart_parking.interfaces.http.dependencies import AppContainer, build_container


def _can_connect_real_mysql(settings: Settings) -> bool:
    """Check if XAMPP MySQL on 127.0.0.1:3306 is reachable from the current process."""
    try:
        import mysql.connector

        conn = mysql.connector.connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci",
            use_pure=True,
            connection_timeout=2,
        )
        conn.close()
        return True
    except Exception:
        return False


def _reset_real_mysql_tables(db: MySQLDatabase) -> None:
    """Truncate/delete all 9 tables safely in FK order on real MySQL test database."""
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        for tbl in (
            "parking_logs",
            "gate_events",
            "session_face_templates",
            "sessions",
            "bookings",
            "parking_slots",
            "user_face_templates",
            "vehicles",
            "users",
        ):
            cursor.execute(f"DELETE FROM `{tbl}`")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
    finally:
        cursor.close()
        conn.close()


class SystemAcceptanceTests(unittest.TestCase):
    """Comprehensive acceptance tests for MySQL repositories, services, concurrency, and FastAPI routes."""

    _use_real_mysql: Optional[bool] = None
    _real_db_initialized: bool = False
    _real_db: Optional[MySQLDatabase] = None

    def setUp(self) -> None:
        self.base_time = datetime(2026, 11, 18, 12, 0, 0, tzinfo=timezone.utc)
        self.settings = Settings(
            capture_sample_count=1,
            capture_timeout_seconds=5,
            mysql_host="127.0.0.1",
            mysql_port=3306,
            mysql_user="root",
            mysql_password="",
            mysql_database="smart_parking_pbl4_test",
            mysql_pool_size=5,
            embedding_secret_key="MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
            embedding_key_version="v1",
            jwt_secret_key="test_jwt_secret_key_pbl4_2026",
            slot_stale_seconds=30,
            booking_ttl_minutes=60,
            session_template_retention_hours=24,
        )
        if SystemAcceptanceTests._use_real_mysql is None:
            SystemAcceptanceTests._use_real_mysql = _can_connect_real_mysql(self.settings)

        if SystemAcceptanceTests._use_real_mysql:
            if not SystemAcceptanceTests._real_db_initialized:
                init_mysql_database(settings=self.settings, drop_existing=True)
                SystemAcceptanceTests._real_db = MySQLDatabase(self.settings)
                SystemAcceptanceTests._real_db_initialized = True
            assert SystemAcceptanceTests._real_db is not None
            self.db = SystemAcceptanceTests._real_db
            _reset_real_mysql_tables(self.db)
        else:
            self.db = SandboxMySQLTestDatabase(self.settings)

        self.container: AppContainer = build_container(settings=self.settings, db=self.db)
        self.app = create_app(container=self.container, enable_background_worker=False)
        self.client = LocalTestClient(self.app)

        # Seed demo data + test fixtures (viet_user, admin, test_user_1, test_user_2, 4 slots Free)
        self.seed_info = seed_demo_data(
            uow=self.container.uow,
            cipher=self.container.cipher,
            settings=self.settings,
            with_test_fixtures=True,
            init_slots_free=True,
            now_utc=self.base_time,
        )

    def tearDown(self) -> None:
        if hasattr(self.db, "_raw_conn"):
            try:
                self.db._raw_conn.close()
            except Exception:
                pass

    def _refresh_all_slots_free(self, now_dt: datetime, sequence: int = 10) -> None:
        self.container.gate_data_service.update_ir_slot_snapshot(
            device_id="ESP32_DEVKIT",
            boot_id="BOOT-TEST-01",
            sequence=sequence,
            slots_payload={"A1": "Free", "A2": "Free", "B1": "Free", "B2": "Free"},
            received_at=now_dt,
        )

    def test_T01_reserved_slot_cannot_be_allocated_to_walkin_or_other_user(self) -> None:
        """T01: Slot physically Free but Reserved cannot be taken by another booking or walk-in guest."""
        now_dt = self.base_time
        self._refresh_all_slots_free(now_dt, sequence=10)

        demo_user = self.seed_info["demo_user"]
        booking = self.container.booking_service.create_booking(
            user_id=demo_user["user_id"],
            vehicle_id=demo_user["vehicle_id"],
            slot_id="A1",
            now_utc=now_dt,
        )
        self.assertEqual(booking["status"], BookingStatus.RESERVED.value)
        self.assertEqual(booking["slot_id"], "A1")

        # Another user tries to book A1 -> 409 SlotNotAvailableException
        test_user_1 = self.seed_info["test_fixtures"][0]
        with self.assertRaises(SlotNotAvailableException) as ctx:
            self.container.booking_service.create_booking(
                user_id=test_user_1["user_id"],
                vehicle_id=test_user_1["vehicle_id"],
                slot_id="A1",
                now_utc=now_dt,
            )
        self.assertEqual(ctx.exception.reason_code, "SLOT_ALREADY_RESERVED")

        # Mark A2, B1, B2 as Occupied physically while A1 remains physically Free (but Reserved)
        self.container.gate_data_service.update_ir_slot_snapshot(
            device_id="ESP32_DEVKIT",
            boot_id="BOOT-TEST-01",
            sequence=11,
            slots_payload={"A1": "Free", "A2": "Occupied", "B1": "Occupied", "B2": "Occupied"},
            received_at=now_dt,
        )

        # Walk-in guest arrives -> must be rejected (ERR_PARKING_FULL), never taking Reserved A1!
        walkin_face = {
            "embedding": make_deterministic_l2_vector(555),
            "liveness_status": "Passed",
            "liveness_score": 0.92,
        }
        with self.assertRaises(SlotNotAvailableException) as walkin_ctx:
            self.container.gate_data_service.allocate_walkin_entry(
                plate_number="92A99999",
                event_id="EV-WALKIN-01",
                session_face_template_data=walkin_face,
                now_utc=now_dt,
            )
        self.assertEqual(walkin_ctx.exception.reason_code, "ERR_PARKING_FULL")

    def test_T02_unknown_fault_or_stale_ir_slot_is_not_available(self) -> None:
        """T02: Slots with Unknown/Fault status or stale last_seen_at cannot be booked."""
        now_dt = self.base_time
        self.container.gate_data_service.update_ir_slot_snapshot(
            device_id="ESP32_DEVKIT",
            boot_id="BOOT-TEST-01",
            sequence=20,
            slots_payload={"A1": "Unknown", "A2": "Fault", "B1": "Free", "B2": "Free"},
            received_at=now_dt,
        )
        demo_user = self.seed_info["demo_user"]

        # A1 is Unknown -> rejected
        with self.assertRaises(SlotNotAvailableException) as ctx_a1:
            self.container.booking_service.create_booking(
                user_id=demo_user["user_id"],
                vehicle_id=demo_user["vehicle_id"],
                slot_id="A1",
                now_utc=now_dt,
            )
        self.assertEqual(ctx_a1.exception.reason_code, "SLOT_SENSOR_STALE_OR_FAULT")

        # A2 is Fault -> rejected
        with self.assertRaises(SlotNotAvailableException) as ctx_a2:
            self.container.booking_service.create_booking(
                user_id=demo_user["user_id"],
                vehicle_id=demo_user["vehicle_id"],
                slot_id="A2",
                now_utc=now_dt,
            )
        self.assertEqual(ctx_a2.exception.reason_code, "SLOT_SENSOR_STALE_OR_FAULT")

        # 45 seconds later (> 30s stale threshold), B1 is Free but stale -> rejected
        stale_time = now_dt + timedelta(seconds=45)
        with self.assertRaises(SlotNotAvailableException) as ctx_b1:
            self.container.booking_service.create_booking(
                user_id=demo_user["user_id"],
                vehicle_id=demo_user["vehicle_id"],
                slot_id="B1",
                now_utc=stale_time,
            )
        self.assertEqual(ctx_b1.exception.reason_code, "SLOT_SENSOR_STALE_OR_FAULT")

    def test_T03_concurrent_booking_same_slot_only_one_succeeds(self) -> None:
        """T03: Two concurrent requests booking slot A1 -> exactly 1 succeeds, 1 gets 409 Conflict."""
        now_dt = self.base_time
        self._refresh_all_slots_free(now_dt, sequence=30)

        u1 = self.seed_info["test_fixtures"][0]
        u2 = self.seed_info["test_fixtures"][1]
        barrier = threading.Barrier(2)
        results: list[tuple[str, object]] = []
        results_lock = threading.Lock()

        def _worker(user_fixture: dict) -> None:
            barrier.wait()
            try:
                res = self.container.booking_service.create_booking(
                    user_id=user_fixture["user_id"],
                    vehicle_id=user_fixture["vehicle_id"],
                    slot_id="A1",
                    now_utc=now_dt,
                )
                with results_lock:
                    results.append(("SUCCESS", res))
            except SlotNotAvailableException as exc:
                with results_lock:
                    results.append(("CONFLICT", exc))

        t1 = threading.Thread(target=_worker, args=(u1,))
        t2 = threading.Thread(target=_worker, args=(u2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        statuses = [r[0] for r in results]
        self.assertEqual(statuses.count("SUCCESS"), 1)
        self.assertEqual(statuses.count("CONFLICT"), 1)

        conflict_exc = next(r[1] for r in results if r[0] == "CONFLICT")
        assert isinstance(conflict_exc, SlotNotAvailableException)
        self.assertEqual(conflict_exc.http_status, 409)
        self.assertEqual(conflict_exc.reason_code, "SLOT_ALREADY_RESERVED")

    def test_T04_reload_countdown_preserves_remaining_seconds(self) -> None:
        """T04: Reloading current booking when 20 minutes remain returns ~1200s, never resetting to 60m."""
        t0 = self.base_time
        self._refresh_all_slots_free(t0, sequence=40)
        demo_user = self.seed_info["demo_user"]

        created = self.container.booking_service.create_booking(
            user_id=demo_user["user_id"],
            vehicle_id=demo_user["vehicle_id"],
            slot_id="B2",
            now_utc=t0,
        )
        self.assertEqual(created["remaining_seconds"], 3600)

        # Simulate page reload 40 minutes later (20 minutes remaining = 1200 seconds)
        t_reload = t0 + timedelta(minutes=40)
        current_res = self.container.booking_service.get_current_booking(
            user_id=demo_user["user_id"],
            now_utc=t_reload,
        )
        booking_dto = current_res["booking"]
        self.assertIsNotNone(booking_dto)
        self.assertEqual(booking_dto["booking_id"], created["booking_id"])
        self.assertEqual(booking_dto["expires_at"], created["expires_at"])
        self.assertEqual(booking_dto["remaining_seconds"], 1200)

    def test_T05_T06_expiry_worker_expires_overdue_but_protects_checkin_pending(self) -> None:
        """
        T05: Overdue Reserved booking (>60m) transitions to Expired and releases active_booking_id.
        T06: Booking that entered Checkin_pending right before expiry is protected from expiry worker.
        """
        t0 = self.base_time
        self._refresh_all_slots_free(t0, sequence=50)
        u1 = self.seed_info["test_fixtures"][0]
        u2 = self.seed_info["test_fixtures"][1]

        # u1 books A1 (will become overdue without check-in)
        b_overdue = self.container.booking_service.create_booking(
            user_id=u1["user_id"],
            vehicle_id=u1["vehicle_id"],
            slot_id="A1",
            now_utc=t0,
        )
        # u2 books A2 (will begin check-in at t0 + 59m50s)
        b_checkin = self.container.booking_service.create_booking(
            user_id=u2["user_id"],
            vehicle_id=u2["vehicle_id"],
            slot_id="A2",
            now_utc=t0,
        )

        # At t0 + 59m50s, u2 arrives at Gate IN and begins check-in
        t_checkin = t0 + timedelta(minutes=59, seconds=50)
        checkin_info = self.container.gate_data_service.begin_booking_checkin(
            plate_number=u2["plate_number"],
            event_id="EV-CHECKIN-NEAR-EXPIRY",
            now_utc=t_checkin,
        )
        self.assertEqual(checkin_info["status"], BookingStatus.CHECKIN_PENDING.value)

        # At t0 + 61m, expiry worker runs
        t_after_60m = t0 + timedelta(minutes=61)
        expired_list = self.container.booking_service.expire_overdue_bookings(now_utc=t_after_60m)
        expired_ids = [item["booking_id"] for item in expired_list]

        # T05: b_overdue is expired and A1 active_booking_id is released
        self.assertIn(b_overdue["booking_id"], expired_ids)
        b1_detail = self.container.booking_service.get_booking_detail(
            booking_id=b_overdue["booking_id"],
            requester_user_id=u1["user_id"],
            now_utc=t_after_60m,
        )
        self.assertEqual(b1_detail["status"], BookingStatus.EXPIRED.value)
        self.assertEqual(b1_detail["slot_id"], "A1")  # History preserved!

        # T06: b_checkin is NOT expired and A2 still holds active_booking_id for u2
        self.assertNotIn(b_checkin["booking_id"], expired_ids)
        b2_detail = self.container.booking_service.get_booking_detail(
            booking_id=b_checkin["booking_id"],
            requester_user_id=u2["user_id"],
            now_utc=t_after_60m,
        )
        self.assertEqual(b2_detail["status"], BookingStatus.CHECKIN_PENDING.value)

    def test_T07_T08_T20_prebooked_flow_session_template_isolation_and_liveness(self) -> None:
        """
        T20: Offline seeded user_face_templates has liveness_status='Not_used', liveness_score=None.
        T07: Pre-booked entry verifies against user_face_templates and creates a dedicated session_face_template.
        T08: Updating user_face_templates while parked does not affect exit verification against session_face_templates.
        """
        t0 = self.base_time
        self._refresh_all_slots_free(t0, sequence=60)
        demo_user = self.seed_info["demo_user"]

        # T20 verification on seeded demo user template
        self.assertEqual(demo_user["liveness_status"], LivenessStatus.NOT_USED.value)

        # Book slot A1
        booking = self.container.booking_service.create_booking(
            user_id=demo_user["user_id"],
            vehicle_id=demo_user["vehicle_id"],
            slot_id="A1",
            now_utc=t0,
        )

        # Vehicle arrives at Gate IN -> begin_booking_checkin
        t_arr = t0 + timedelta(minutes=5)
        checkin = self.container.gate_data_service.begin_booking_checkin(
            plate_number=demo_user["plate_number"],
            event_id="EV-GATE-IN-001",
            now_utc=t_arr,
        )
        self.assertNotIn("reference_embedding", checkin)

        # Live camera captures driver face vector at Gate IN (Liveness Passed)
        entry_session_vector = make_deterministic_l2_vector(seed=7777)
        entry_perm = self.container.gate_data_service.confirm_booking_entry_permission(
            booking_id=booking["booking_id"],
            event_id="EV-GATE-IN-001",
            session_face_template_data={
                "embedding": entry_session_vector,
                "liveness_status": "Passed",
                "liveness_score": 0.97,
                "quality_score": 0.91,
            },
            command_id="CMD-OPEN-IN-001",
            ocr_confidence=0.98,
            now_utc=t_arr,
        )
        session_id = entry_perm["session_id"]
        self.assertEqual(entry_perm["status"], SessionStatus.ENTRY_PENDING.value)

        # Vehicle physically passes Gate IN barrier
        t_pass_in = t_arr + timedelta(seconds=4)
        pass_in = self.container.gate_data_service.confirm_gate_in_passage(
            event_id="EV-GATE-IN-001",
            now_utc=t_pass_in,
        )
        self.assertEqual(pass_in["session_status"], SessionStatus.ACTIVE.value)
        self.assertEqual(pass_in["parking_status"], ParkingStatus.PARKING_PENDING.value)

        # T13: Replay confirm_gate_in_passage with same event_id -> idempotent, entry_time unchanged
        replay_in = self.container.gate_data_service.confirm_gate_in_passage(
            event_id="EV-GATE-IN-001",
            now_utc=t_pass_in + timedelta(seconds=10),
        )
        self.assertTrue(replay_in["idempotent_replay"])
        self.assertEqual(replay_in["entry_time"], pass_in["entry_time"])

        # IR sensor reports car parked in A1 -> Parking_pending -> Parked_confirmed
        t_parked = t_pass_in + timedelta(seconds=15)
        ir_res = self.container.gate_data_service.update_ir_slot_snapshot(
            device_id="ESP32_DEVKIT",
            boot_id="BOOT-TEST-01",
            sequence=61,
            slots_payload={"A1": "Occupied", "A2": "Free", "B1": "Free", "B2": "Free"},
            received_at=t_parked,
        )
        self.assertEqual(
            ir_res["session_transitions"][0]["new_parking_status"],
            ParkingStatus.PARKED_CONFIRMED.value,
        )

        # T08: While car is parked in A1, offline tool updates user_face_templates with a new vector
        new_account_vector = make_deterministic_l2_vector(seed=9999)
        self.assertFalse(np.allclose(entry_session_vector, new_account_vector))
        tpl_update = self.container.gate_data_service.update_user_face_template_offline(
            user_id=demo_user["user_id"],
            vector_np=new_account_vector,
            liveness_status="Not_used",
            liveness_score=0.99,  # Must be forced to None when Not_used (T20)
            now_utc=t_parked + timedelta(minutes=10),
        )
        self.assertEqual(tpl_update["liveness_status"], LivenessStatus.NOT_USED.value)
        self.assertIsNone(tpl_update["liveness_score"])

        # Vehicle arrives at Gate OUT -> prepare_exit_verification MUST return entry_session_vector
        t_exit = t_parked + timedelta(minutes=25)
        exit_prep = self.container.gate_data_service.prepare_exit_verification(
            plate_number=demo_user["plate_number"],
            event_id="EV-GATE-OUT-001",
            now_utc=t_exit,
        )
        self.assertEqual(exit_prep["template_source"], "session_face_templates")
        self.assertTrue(np.allclose(exit_prep["entry_embedding"], entry_session_vector, atol=1e-6))
        self.assertFalse(np.allclose(exit_prep["entry_embedding"], new_account_vector, atol=1e-3))

        # Approve exit permission (Session becomes Exit_pending)
        self.container.gate_data_service.approve_exit_permission(
            session_id=session_id,
            event_id="EV-GATE-OUT-001",
            command_id="CMD-OPEN-OUT-001",
            now_utc=t_exit,
        )

        # T15: Car backs out of A1 so IR sensor reports A1='Free', but car hasn't passed Gate OUT yet
        self.container.gate_data_service.update_ir_slot_snapshot(
            device_id="ESP32_DEVKIT",
            boot_id="BOOT-TEST-01",
            sequence=62,
            slots_payload={"A1": "Free", "A2": "Free", "B1": "Free", "B2": "Free"},
            received_at=t_exit + timedelta(seconds=2),
        )
        # Another user tries to book A1 while car is still Exit_pending -> must be rejected (T15)!
        u1 = self.seed_info["test_fixtures"][0]
        with self.assertRaises(SlotNotAvailableException) as t15_ctx:
            self.container.booking_service.create_booking(
                user_id=u1["user_id"],
                vehicle_id=u1["vehicle_id"],
                slot_id="A1",
                now_utc=t_exit + timedelta(seconds=3),
            )
        self.assertEqual(t15_ctx.exception.reason_code, "SLOT_ASSIGNED_TO_SESSION")

        # Car completes passage through Gate OUT -> session Closed, booking Completed, slot released
        t_pass_out = t_exit + timedelta(seconds=6)
        pass_out = self.container.gate_data_service.confirm_gate_out_passage(
            event_id="EV-GATE-OUT-001",
            now_utc=t_pass_out,
        )
        self.assertEqual(pass_out["session_status"], SessionStatus.CLOSED.value)

        # T19: Retention purge after 25 hours removes Closed session's session_face_template
        # while keeping user_face_templates intact
        t_retention = t_pass_out + timedelta(hours=25)
        purge_res = self.container.retention_service.purge_expired_session_templates(now_utc=t_retention)
        self.assertEqual(purge_res["purged_count"], 1)

        profile_after = self.container.auth_service.get_current_user_profile(demo_user["user_id"])
        self.assertTrue(profile_after["face_template"]["has_active_template"])

    def test_VII4_http_rbac_and_role_based_slot_privacy(self) -> None:
        """
        VII.4:
        - USER token calling /api/admin/* receives 403 Forbidden.
        - USER calling GET /api/slots does NOT see another user's plate_number or booking_id.
        - ADMIN calling GET /api/slots sees full booking & plate details.
        - USER cannot cancel another user's booking (403 Forbidden).
        """
        self._refresh_all_slots_free(utc_now(), sequence=70)

        # Login as viet_user and book A1
        user_client = LocalTestClient(self.app)
        login_viet = user_client.post(
            "/api/auth/login",
            json={"username": "viet_user", "password": "Viet@123"},
        )
        self.assertEqual(login_viet.status_code, 200)
        viet_token = login_viet.json()["access_token"]
        viet_vehicle_id = login_viet.json()["user"]["vehicles"][0]["vehicle_id"]

        book_resp = user_client.post(
            "/api/bookings",
            json={"vehicle_id": viet_vehicle_id, "slot_id": "A1"},
            headers={"Authorization": f"Bearer {viet_token}"},
        )
        self.assertEqual(book_resp.status_code, 201)
        booking_id = book_resp.json()["booking_id"]

        # USER calling /api/admin/sessions -> 403 Forbidden
        admin_attempt = user_client.get(
            "/api/admin/sessions",
            headers={"Authorization": f"Bearer {viet_token}"},
        )
        self.assertEqual(admin_attempt.status_code, 403)
        self.assertEqual(admin_attempt.json()["reason_code"], "ADMIN_ROLE_REQUIRED")

        # Login as test_user_1 and inspect GET /api/slots -> A1 details must be masked!
        other_client = LocalTestClient(self.app)
        login_other = other_client.post(
            "/api/auth/login",
            json={"username": "test_user_1", "password": "Test@123"},
        )
        self.assertEqual(login_other.status_code, 200)
        other_token = login_other.json()["access_token"]

        slots_for_other = other_client.get(
            "/api/slots",
            headers={"Authorization": f"Bearer {other_token}"},
        ).json()
        a1_other = next(s for s in slots_for_other["slots"] if s["slot_id"] == "A1")
        self.assertEqual(a1_other["display_status"], "RESERVED")
        self.assertEqual(a1_other["label_vi"], "Đã được đặt")
        self.assertIsNone(a1_other["booking_id"])
        self.assertIsNone(a1_other["plate_number"])

        # test_user_1 tries to cancel viet_user's booking -> 403 Forbidden
        cancel_other = other_client.post(
            f"/api/bookings/{booking_id}/cancel",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        self.assertEqual(cancel_other.status_code, 403)

        # Login as ADMIN and inspect GET /api/slots -> sees full details for A1
        admin_client = LocalTestClient(self.app)
        login_admin = admin_client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "Admin@123"},
        )
        self.assertEqual(login_admin.status_code, 200)
        admin_token = login_admin.json()["access_token"]

        slots_for_admin = admin_client.get(
            "/api/slots",
            headers={"Authorization": f"Bearer {admin_token}"},
        ).json()
        a1_admin = next(s for s in slots_for_admin["slots"] if s["slot_id"] == "A1")
        self.assertEqual(a1_admin["booking_id"], booking_id)
        self.assertEqual(a1_admin["plate_number"], "43A12345")
        self.assertEqual(a1_admin["booked_by_username"], "viet_user")

    def test_lock_order_enforcer_embedding_cipher_and_log_sanitization(self) -> None:
        """Verify deadlock lock-order enforcement, AES-256-GCM vector validation, and log sanitization."""
        tracker = LockOrderTracker()
        tracker.record_lock("parking_slots")  # Rank 2
        with self.assertRaises(LockOrderViolationError):
            tracker.record_lock("vehicles")  # Rank 1 after Rank 2 -> must raise!

        cipher = self.container.cipher
        # Unnormalized vector must be rejected
        bad_vec = np.ones(512, dtype=np.float32)
        with self.assertRaises(ValueError):
            cipher.encrypt_embedding(bad_vec)

        # Wrong dimension must be rejected
        with self.assertRaises(ValueError):
            cipher.encrypt_embedding(np.ones(128, dtype=np.float32))

        # Valid 512-D L2 vector encrypts & decrypts losslessly
        valid_vec = make_deterministic_l2_vector(seed=42)
        blob, meta = cipher.encrypt_embedding(valid_vec, key_version="v1")
        restored = cipher.decrypt_embedding(blob, meta)
        self.assertTrue(np.allclose(valid_vec, restored, atol=1e-6))

        # Audit log details sanitization strips passwords, secret keys, and embeddings
        dirty = {
            "username": "viet_user",
            "password": "secret",
            "password_hash": "$2b$12$...",
            "embedding_blob": b"raw_bytes",
            "nested": {"jwt_secret_key": "hidden", "slot_id": "A1"},
        }
        cleaned = sanitize_log_details(dirty)
        assert cleaned is not None
        self.assertNotIn("password", cleaned)
        self.assertNotIn("password_hash", cleaned)
        self.assertNotIn("embedding_blob", cleaned)
        self.assertNotIn("jwt_secret_key", cleaned["nested"])
        self.assertEqual(cleaned["nested"]["slot_id"], "A1")

    def test_manual_review_decision_and_duplicate_protection(self) -> None:
        """Verify ADMIN manual review approval/denial, audit logging, and duplicate review prevention."""
        now_dt = utc_now()
        self._refresh_all_slots_free(now_dt, sequence=80)

        # Flag a gate event requiring manual review
        flagged = self.container.gate_data_service.flag_gate_review_required(
            event_id="EV-REVIEW-001",
            gate_id="OUT",
            device_id="GATE_OUT_CAM",
            reason_code="ERR_FACE_UNCERTAIN",
            liveness_status="Passed",
            liveness_score=0.88,
            now_utc=now_dt,
        )
        self.assertEqual(flagged["decision"], "Review_required")

        admin_client = LocalTestClient(self.app)
        login_admin = admin_client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "Admin@123"},
        )
        admin_token = login_admin.json()["access_token"]

        reviews_res = admin_client.get(
            "/api/admin/reviews",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        self.assertEqual(reviews_res.status_code, 200)
        self.assertEqual(reviews_res.json()["count"], 1)

        decide_res = admin_client.post(
            "/api/admin/reviews/EV-REVIEW-001/decision",
            json={"action": "APPROVE", "reason": "Đã kiểm tra thẻ sinh viên & giấy đăng ký xe"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # An old database event without a live device turn must never open a gate.
        self.assertEqual(decide_res.status_code, 409)
        self.assertEqual(decide_res.json()["reason_code"], "REVIEW_TURN_STALE")
        denied_res = admin_client.post(
            "/api/admin/reviews/EV-REVIEW-001/decision",
            json={"action": "DENY", "reason": "No live gate turn; deny stale event"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        self.assertEqual(denied_res.status_code, 200)
        self.assertEqual(denied_res.json()["decision"], "Denied")

        # Duplicate decision on already decided event must be rejected with 409
        dup_res = admin_client.post(
            "/api/admin/reviews/EV-REVIEW-001/decision",
            json={"action": "DENY", "reason": "Bấm nhầm lần 2"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        self.assertEqual(dup_res.status_code, 409)
        self.assertEqual(dup_res.json()["reason_code"], "REVIEW_ALREADY_DECIDED")

    def test_ir_snapshot_deduplication_and_wrong_slot_parking_anomaly(self) -> None:
        """Verify stale/duplicate IR sequence deduplication and wrong-slot Parking_review_required transition."""
        now_dt = self.base_time
        self._refresh_all_slots_free(now_dt, sequence=100)

        # Duplicate sequence 100 in same boot_id -> rejected
        dup_snap = self.container.gate_data_service.update_ir_slot_snapshot(
            device_id="ESP32_DEVKIT",
            boot_id="BOOT-TEST-01",
            sequence=100,
            slots_payload={"A1": "Occupied", "A2": "Free", "B1": "Free", "B2": "Free"},
            received_at=now_dt + timedelta(seconds=1),
        )
        self.assertFalse(dup_snap["accepted"])
        self.assertEqual(dup_snap["reason"], "STALE_OR_DUPLICATE_SEQUENCE")

        # Walk-in car enters and is assigned slot A1 (deterministic_choice=True)
        walkin_res = self.container.gate_data_service.allocate_walkin_entry(
            plate_number="43A55555",
            event_id="EV-WALKIN-ANOMALY",
            session_face_template_data={
                "embedding": make_deterministic_l2_vector(333),
                "liveness_status": "Passed",
                "liveness_score": 0.95,
            },
            deterministic_choice=True,
            now_utc=now_dt + timedelta(seconds=2),
        )
        self.assertEqual(walkin_res["assigned_slot_id"], "A1")
        self.container.gate_data_service.confirm_gate_in_passage(
            event_id="EV-WALKIN-ANOMALY",
            now_utc=now_dt + timedelta(seconds=5),
        )

        # Car parks in wrong slot B2 instead of assigned A1
        anomaly_snap = self.container.gate_data_service.update_ir_slot_snapshot(
            device_id="ESP32_DEVKIT",
            boot_id="BOOT-TEST-01",
            sequence=101,
            slots_payload={"A1": "Free", "A2": "Free", "B1": "Free", "B2": "Occupied"},
            received_at=now_dt + timedelta(seconds=12),
        )
        self.assertTrue(anomaly_snap["accepted"])
        self.assertEqual(
            anomaly_snap["session_transitions"][0]["new_parking_status"],
            ParkingStatus.PARKING_REVIEW_REQUIRED.value,
        )
        # Assigned slot on session remains A1 (never silently overwritten!)
        self.assertEqual(anomaly_snap["session_transitions"][0]["assigned_slot_id"], "A1")

    def test_booking_cancellation_and_personal_history_api(self) -> None:
        """Verify booking cancellation releases slot while preserving history, and blocks cancel during checkin."""
        now_dt = utc_now()
        self._refresh_all_slots_free(now_dt, sequence=110)

        user_client = LocalTestClient(self.app)
        login_res = user_client.post(
            "/api/auth/login",
            json={"username": "viet_user", "password": "Viet@123"},
        )
        token = login_res.json()["access_token"]
        vehicle_id = login_res.json()["user"]["vehicles"][0]["vehicle_id"]

        # Create booking on B1 and cancel it
        b1_res = user_client.post(
            "/api/bookings",
            json={"vehicle_id": vehicle_id, "slot_id": "B1"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(b1_res.status_code, 201)
        b1_id = b1_res.json()["booking_id"]

        cancel_res = user_client.post(
            f"/api/bookings/{b1_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(cancel_res.status_code, 200)
        self.assertEqual(cancel_res.json()["status"], BookingStatus.CANCELLED.value)
        self.assertEqual(cancel_res.json()["slot_id"], "B1")

        # B1 is now immediately bookable again!
        b2_res = user_client.post(
            "/api/bookings",
            json={"vehicle_id": vehicle_id, "slot_id": "B1"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(b2_res.status_code, 201)
        b2_id = b2_res.json()["booking_id"]

        # Begin check-in at Gate IN -> cancel must now be rejected (409 BOOKING_CANNOT_BE_CANCELLED)
        self.container.gate_data_service.begin_booking_checkin(
            plate_number="43A12345",
            event_id="EV-CHECKIN-BLOCK-CANCEL",
            now_utc=now_dt + timedelta(seconds=5),
        )
        blocked_cancel = user_client.post(
            f"/api/bookings/{b2_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(blocked_cancel.status_code, 409)
        self.assertEqual(blocked_cancel.json()["reason_code"], "BOOKING_CANNOT_BE_CANCELLED")

        # Personal history returns both bookings for viet_user
        hist_res = user_client.get(
            "/api/me/history",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(hist_res.status_code, 200)
        self.assertEqual(len(hist_res.json()["bookings"]), 2)

    def test_logout_revokes_bearer_token_immediately(self) -> None:
        """Verify POST /api/auth/logout revokes Bearer JWT server-side so subsequent calls return 401."""
        user_client = LocalTestClient(self.app)
        login_res = user_client.post(
            "/api/auth/login",
            json={"username": "viet_user", "password": "Viet@123"},
        )
        self.assertEqual(login_res.status_code, 200)
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        me_before = user_client.get("/api/me", headers=headers)
        self.assertEqual(me_before.status_code, 200)

        logout_res = user_client.post("/api/auth/logout", headers=headers)
        self.assertEqual(logout_res.status_code, 200)

        me_after = user_client.get("/api/me", headers=headers)
        self.assertEqual(me_after.status_code, 401)
        self.assertEqual(me_after.json()["reason_code"], "TOKEN_REVOKED")

    def test_idempotency_key_and_expired_booking_cancel_rejected(self) -> None:
        """Verify X-Idempotency-Key deduplicates booking retries and expired bookings cannot be cancelled."""
        t0 = utc_now()
        self._refresh_all_slots_free(t0, sequence=120)
        demo_user = self.seed_info["demo_user"]

        idem_key = "idem-test-slot-A2-001"
        b_first = self.container.booking_service.create_booking(
            user_id=demo_user["user_id"],
            vehicle_id=demo_user["vehicle_id"],
            slot_id="A2",
            idempotency_key=idem_key,
            now_utc=t0,
        )
        b_retry = self.container.booking_service.create_booking(
            user_id=demo_user["user_id"],
            vehicle_id=demo_user["vehicle_id"],
            slot_id="A2",
            idempotency_key=idem_key,
            now_utc=t0 + timedelta(seconds=2),
        )
        self.assertEqual(b_first["booking_id"], b_retry["booking_id"])

        # Attempting to cancel after 61 minutes (already expired before worker ran) must raise 409 BOOKING_ALREADY_EXPIRED
        with self.assertRaises(BookingConflictException) as ctx:
            self.container.booking_service.cancel_booking(
                booking_id=b_first["booking_id"],
                requester_user_id=demo_user["user_id"],
                now_utc=t0 + timedelta(minutes=61),
            )
        self.assertEqual(ctx.exception.reason_code, "BOOKING_ALREADY_EXPIRED")

    def test_deny_gate_event_and_cancel_unpassed_entry_session(self) -> None:
        """Verify gate failure/timeout rollback hooks keep booking & slot states clean."""
        t0 = self.base_time
        self._refresh_all_slots_free(t0, sequence=130)
        demo_user = self.seed_info["demo_user"]

        booking = self.container.booking_service.create_booking(
            user_id=demo_user["user_id"],
            vehicle_id=demo_user["vehicle_id"],
            slot_id="B2",
            now_utc=t0,
        )
        # Step 1: Begin check-in -> Checkin_pending, then AI denies (liveness failed) -> reverts to Reserved!
        self.container.gate_data_service.begin_booking_checkin(
            plate_number=demo_user["plate_number"],
            event_id="EV-DENY-001",
            now_utc=t0 + timedelta(minutes=2),
        )
        deny_res = self.container.gate_data_service.deny_gate_event(
            event_id="EV-DENY-001",
            gate_id="IN",
            device_id="GATE_IN",
            reason_code="ERR_FACE_LIVENESS_FAILED",
            booking_id=booking["booking_id"],
            liveness_status="Failed",
            liveness_score=0.12,
            now_utc=t0 + timedelta(minutes=2, seconds=2),
        )
        self.assertEqual(deny_res["decision"], "Denied")
        b_after_deny = self.container.booking_service.get_booking_detail(
            booking_id=booking["booking_id"],
            requester_user_id=demo_user["user_id"],
            now_utc=t0 + timedelta(minutes=2, seconds=3),
        )
        self.assertEqual(b_after_deny["status"], BookingStatus.RESERVED.value)

        # Step 2: Retry check-in -> Approved Entry_pending, but car never drives through gate -> cancel_unpassed_entry_session!
        self.container.gate_data_service.begin_booking_checkin(
            plate_number=demo_user["plate_number"],
            event_id="EV-TIMEOUT-002",
            now_utc=t0 + timedelta(minutes=5),
        )
        self.container.gate_data_service.confirm_booking_entry_permission(
            booking_id=booking["booking_id"],
            event_id="EV-TIMEOUT-002",
            session_face_template_data={
                "embedding": make_deterministic_l2_vector(888),
                "liveness_status": "Passed",
                "liveness_score": 0.94,
            },
            now_utc=t0 + timedelta(minutes=5, seconds=1),
        )
        cancel_sess = self.container.gate_data_service.cancel_unpassed_entry_session(
            event_id="EV-TIMEOUT-002",
            reason_code="ERR_GATE_TIMEOUT",
            now_utc=t0 + timedelta(minutes=6),
        )
        self.assertEqual(cancel_sess["session_status"], SessionStatus.CANCELLED.value)
        # Booking reverts to Reserved (still within 60m) and slot.reserved_session_id is freed
        b_after_timeout = self.container.booking_service.get_booking_detail(
            booking_id=booking["booking_id"],
            requester_user_id=demo_user["user_id"],
            now_utc=t0 + timedelta(minutes=6, seconds=1),
        )
        self.assertEqual(b_after_timeout["status"], BookingStatus.RESERVED.value)

    def test_driver_navigation_four_routes_and_no_hardware_side_effects(self) -> None:
        """
        Verify First-Person Driver Navigation geometry for all 4 slots (A1, A2, B1, B2),
        ensure zero hardware/API side-effect calls in FirstPersonDriverModal.tsx,
        and confirm serve_frontend.py compiles cleanly with zero leftover import.meta tokens.
        """
        import json
        import re

        repo_root = _EDGE_ROOT.parent
        routes_json_path = repo_root / "contracts" / "driver-routes.json"
        self.assertTrue(routes_json_path.is_file())
        routes_data = json.loads(routes_json_path.read_text(encoding="utf-8"))["routes"]
        self.assertEqual(set(routes_data.keys()), {"A1", "A2", "B1", "B2"})

        # Verify distinct accurate directions & distances for all 4 slots
        self.assertEqual(routes_data["A1"]["row"], "A")
        self.assertEqual(routes_data["A1"]["turnDirection"], "LEFT")
        self.assertFalse(routes_data["A1"]["passesRowA"])
        self.assertLess(routes_data["A1"]["steeringPeakDeg"], 0)

        self.assertEqual(routes_data["A2"]["row"], "A")
        self.assertEqual(routes_data["A2"]["turnDirection"], "RIGHT")
        self.assertFalse(routes_data["A2"]["passesRowA"])
        self.assertGreater(routes_data["A2"]["steeringPeakDeg"], 0)

        self.assertEqual(routes_data["B1"]["row"], "B")
        self.assertEqual(routes_data["B1"]["turnDirection"], "LEFT")
        self.assertTrue(routes_data["B1"]["passesRowA"])
        self.assertGreater(routes_data["B1"]["distanceMeters"], routes_data["A1"]["distanceMeters"])

        self.assertEqual(routes_data["B2"]["row"], "B")
        self.assertEqual(routes_data["B2"]["turnDirection"], "RIGHT")
        self.assertTrue(routes_data["B2"]["passesRowA"])
        self.assertGreater(routes_data["B2"]["distanceMeters"], routes_data["A2"]["distanceMeters"])

        # Safety invariant: FirstPersonDriverModal.tsx MUST NOT invoke fetch, ApiClient, or any backend/hardware API
        modal_src = (
            repo_root / "dashboard" / "src" / "features" / "user-portal" / "FirstPersonDriverModal.tsx"
        ).read_text(encoding="utf-8")
        self.assertNotIn("fetch(", modal_src)
        self.assertNotIn("ApiClient", modal_src)
        self.assertNotIn("/api/", modal_src)
        self.assertNotIn("geolocation", modal_src.lower())

        # Verify serve_frontend.py assembles all TS/TSX modules cleanly with zero leftover import.meta
        dashboard_dir = repo_root / "dashboard"
        if str(dashboard_dir) not in sys.path:
            sys.path.insert(0, str(dashboard_dir))
        try:
            import serve_frontend
        except ModuleNotFoundError as exc:
            if exc.name in ("fastapi", "uvicorn"):
                self.skipTest("Frontend serving check requires FastAPI and uvicorn")
            raise

        html = serve_frontend.build_spa_html()
        self.assertIn("@babel/standalone@7.24.7", html)
        self.assertNotIn("import.meta.env", html)
        self.assertNotIn("allExtensions", html)
        self.assertNotIn("isTSX", html)
        self.assertIn("FirstPersonDriverModal", html)
        self.assertIn("DRIVER_ROUTES", html)

        # Verify unified FastAPI app mounts /, /login, /user, /admin returning HTTP 200 HTML
        for spa_path in ("/", "/login", "/user", "/admin"):
            spa_resp = self.client.get(spa_path)
            self.assertEqual(spa_resp.status_code, 200, f"Expected 200 on unified SPA route {spa_path}")
            body_text = getattr(spa_resp, "text", "") or str(spa_resp.json() if hasattr(spa_resp, "json") else "")
            dist_index = dashboard_dir / "dist" / "index.html"
            if dist_index.is_file():
                self.assertEqual(body_text, dist_index.read_text(encoding="utf-8"))
                assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', body_text)
                self.assertTrue(assets, "Vite HTML must reference its built assets")
                for asset_path in assets:
                    self.assertEqual(self.client.get(asset_path).status_code, 200, asset_path)
            else:
                self.assertIn("@babel/standalone@7.24.7", body_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
