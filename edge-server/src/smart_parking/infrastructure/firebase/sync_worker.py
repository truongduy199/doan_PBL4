"""Cloud Sync Worker.

Định kỳ hoặc theo sự kiện quét hàng đợi outbox từ SQLite để đẩy lên Firebase Realtime Database.
"""

import json
import logging
import time
from typing import Optional
from smart_parking.infrastructure.firebase.firebase_client import FirebaseClient

logger = logging.getLogger(__name__)


class SyncWorker:
    """Worker đồng bộ dữ liệu Outbox lên Firebase Realtime Database."""

    def __init__(self, firebase_client: FirebaseClient, outbox_repo=None):
        self.firebase_client = firebase_client
        self.outbox_repo = outbox_repo

    def process_outbox_queue(self) -> int:
        """Đọc và xử lý các bản ghi pending trong hàng đợi outbox."""
        if not self.outbox_repo:
            return 0

        pending_items = self.outbox_repo.get_pending_events()
        processed_count = 0

        for item in pending_items:
            event_type = item.get("event_type")
            payload = item.get("payload", {})
            success = False

            if event_type == "SLOT_UPDATE":
                success = self.firebase_client.sync_slot(
                    slot_id=payload.get("slot_id"),
                    status=payload.get("status"),
                    current_plate=payload.get("current_plate"),
                    assigned_session_id=payload.get("assigned_session_id"),
                )
            elif event_type == "SESSION_UPDATE":
                success = self.firebase_client.sync_session(
                    session_id=payload.get("session_id"),
                    plate_number=payload.get("plate_number"),
                    slot_id=payload.get("slot_id"),
                    status=payload.get("status"),
                    entry_time=payload.get("entry_time"),
                    exit_time=payload.get("exit_time"),
                )

            if success:
                self.outbox_repo.mark_sent(item.get("id"))
                processed_count += 1
            else:
                self.outbox_repo.increment_retry(item.get("id"))

        return processed_count