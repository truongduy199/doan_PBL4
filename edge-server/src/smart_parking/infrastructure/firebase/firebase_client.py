"""Firebase Realtime Database Client.

Hỗ trợ đồng bộ hai chiều qua Firebase REST API hoặc Firebase Admin SDK.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


class FirebaseClient:
    """Client giao tiếp với Firebase Realtime Database."""

    def __init__(
        self,
        database_url: str = "https://smart-parking-pbl4-default-rtdb.firebaseio.com",
        credentials_path: Optional[str] = None,
    ):
        self.database_url = database_url.rstrip("/")
        self.credentials_path = credentials_path
        self._use_admin_sdk = False

        if credentials_path:
            try:
                import firebase_admin
                from firebase_admin import credentials, db

                if not firebase_admin._apps:
                    cred = credentials.Certificate(credentials_path)
                    firebase_admin.initialize_app(cred, {"databaseURL": self.database_url})
                self._use_admin_sdk = True
                logger.info("Firebase Admin SDK initialized successfully.")
            except Exception as e:
                logger.warning(f"Could not init Firebase Admin SDK ({e}), falling back to REST API.")

    def _rest_request(self, path: str, method: str = "PUT", data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Thực hiện HTTP REST request tới Firebase Realtime Database."""
        url = f"{self.database_url}/{path.lstrip('/')}.json"
        body = json.dumps(data).encode("utf-8") if data is not None else None

        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                res_body = response.read().decode("utf-8")
                return json.loads(res_body) if res_body else {}
        except urllib.error.URLError as e:
            logger.error(f"Firebase REST request failed [{method} {url}]: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during Firebase REST request: {e}")
            return None

    def sync_slot(
        self,
        slot_id: str,
        status: str,
        current_plate: Optional[str] = None,
        assigned_session_id: Optional[str] = None,
    ) -> bool:
        """Đồng bộ trạng thái của một ô đỗ (A1, A2, B1, B2) lên Firebase."""
        payload = {
            "slot_id": slot_id,
            "status": status,
            "current_plate": current_plate,
            "assigned_session_id": assigned_session_id,
            "updated_at": datetime.now().isoformat(),
        }

        if self._use_admin_sdk:
            try:
                from firebase_admin import db
                ref = db.reference(f"parking_slots/{slot_id}")
                ref.set(payload)
                return True
            except Exception as e:
                logger.error(f"Admin SDK sync_slot failed: {e}")
                return False

        res = self._rest_request(f"parking_slots/{slot_id}", method="PUT", data=payload)
        return res is not None

    def sync_session(
        self,
        session_id: str,
        plate_number: str,
        slot_id: str,
        status: str,
        entry_time: Optional[str] = None,
        exit_time: Optional[str] = None,
    ) -> bool:
        """Đồng bộ thông tin phiên đỗ xe lên Firebase."""
        payload = {
            "session_id": session_id,
            "plate_number": plate_number,
            "slot_id": slot_id,
            "status": status,
            "entry_time": entry_time or datetime.now().strftime("%H:%M:%S"),
            "exit_time": exit_time,
        }

        if self._use_admin_sdk:
            try:
                from firebase_admin import db
                ref = db.reference(f"parking_sessions/{session_id}")
                ref.set(payload)
                return True
            except Exception as e:
                logger.error(f"Admin SDK sync_session failed: {e}")
                return False

        res = self._rest_request(f"parking_sessions/{session_id}", method="PUT", data=payload)
        return res is not None

    def create_review_request(
        self,
        request_id: str,
        session_id: str,
        plate_number: str,
        reason_code: str,
        similarity_score: float,
    ) -> bool:
        """Tạo yêu cầu duyệt thủ công khi khuôn mặt ở vùng không chắc chắn."""
        payload = {
            "request_id": request_id,
            "session_id": session_id,
            "plate_number": plate_number,
            "reason_code": reason_code,
            "similarity_score": round(similarity_score, 4),
            "status": "PENDING",
            "created_at": datetime.now().strftime("%H:%M:%S"),
        }

        res = self._rest_request(f"review_requests/{request_id}", method="PUT", data=payload)
        return res is not None

    def log_event(self, event_type: str, title: str, description: str, severity: str = "info") -> bool:
        """Ghi nhật ký sự kiện thời gian thực lên Firebase."""
        event_id = f"evt_{int(datetime.now().timestamp() * 1000)}"
        payload = {
            "id": event_id,
            "type": event_type,
            "title": title,
            "description": description,
            "severity": severity,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }
        res = self._rest_request(f"events/{event_id}", method="PUT", data=payload)
        return res is not None