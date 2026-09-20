"""Review Request Listener.

Lắng nghe các quyết định duyệt thủ công từ Dashboard qua Firebase Realtime Database.
"""

import json
import logging
import threading
import time
from typing import Callable, Dict, Optional, Set
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


class ReviewListener:
    """Lắng nghe các thay đổi tại node review_requests trên Firebase."""

    def __init__(
        self,
        database_url: str = "https://smart-parking-pbl4-default-rtdb.firebaseio.com",
        poll_interval: float = 1.0,
    ):
        self.database_url = database_url.rstrip("/")
        self.poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._handled_decisions: Set[str] = set()

    def start(self, on_decision: Callable[[str, str, Dict], None]):
        """Bắt đầu luồng lắng nghe thời gian thực.
        
        Args:
            on_decision: Hàm callback(request_id, status, request_data)
        """
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, args=(on_decision,), daemon=True)
        self._thread.start()
        logger.info("ReviewListener started in background thread.")

    def stop(self):
        """Dừng lắng nghe."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("ReviewListener stopped.")

    def _listen_loop(self, on_decision: Callable[[str, str, Dict], None]):
        url = f"{self.database_url}/review_requests.json"

        while self._running:
            try:
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=3) as response:
                    body = response.read().decode("utf-8")
                    if body and body != "null":
                        requests_map = json.loads(body)
                        if isinstance(requests_map, dict):
                            for req_id, req_data in requests_map.items():
                                if not isinstance(req_data, dict):
                                    continue
                                status = req_data.get("status")
                                if status in ("APPROVED", "REJECTED"):
                                    event_key = f"{req_id}:{status}"
                                    if event_key not in self._handled_decisions:
                                        self._handled_decisions.add(event_key)
                                        logger.info(f"Received review decision from Dashboard: {req_id} -> {status}")
                                        on_decision(req_id, status, req_data)
            except urllib.error.URLError:
                pass  # Network temporary timeout
            except Exception as e:
                logger.error(f"Error in ReviewListener loop: {e}")

            time.sleep(self.poll_interval)