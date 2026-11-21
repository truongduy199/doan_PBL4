"""Realtime Event Bus for WebSocket and Server-Sent Events (SSE) notifications after DB commits."""
from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

from smart_parking.infrastructure.database.mysql_db import format_utc_iso, format_vn_iso, utc_now

logger = logging.getLogger(__name__)


class RealtimeEventBus:
    """In-process pub/sub event bus broadcasting state changes after MySQL transaction commits."""

    def __init__(self) -> None:
        self._queues: Set[asyncio.Queue] = set()
        self._sync_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._queue_loops: Dict[asyncio.Queue, asyncio.AbstractEventLoop] = {}
        self._lock = threading.RLock()

    def subscribe_queue(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        with self._lock:
            self._queues.add(q)
            self._queue_loops[q] = asyncio.get_running_loop()
        return q

    def unsubscribe_queue(self, q: asyncio.Queue) -> None:
        with self._lock:
            self._queues.discard(q)
            self._queue_loops.pop(q, None)

    def add_listener(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        self._sync_callbacks.append(callback)

    def publish(
        self,
        event_type: str,
        payload: Dict[str, Any],
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Publish an event immediately after a MySQL transaction commit."""
        ts = now_utc or utc_now()
        envelope: Dict[str, Any] = {
            "event_type": event_type,
            "server_time": format_utc_iso(ts),
            "server_time_vn": format_vn_iso(ts),
            "payload": payload,
        }
        for cb in list(self._sync_callbacks):
            try:
                cb(envelope)
            except Exception as exc:
                logger.debug("Sync event listener error: %s", exc)

        def enqueue(q: asyncio.Queue) -> None:
            with self._lock:
                if q not in self._queues:
                    return
                if q.full():
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                q.put_nowait(envelope)
        with self._lock:
            subscribers = list(self._queue_loops.items())
        for q, loop in subscribers:
            try:
                loop.call_soon_threadsafe(enqueue, q)
            except RuntimeError:
                self.unsubscribe_queue(q)

        return envelope


# Legacy alias for backwards compatibility
EventService = RealtimeEventBus
