"""Realtime WebSocket (/api/ws) and Server-Sent Events (/api/events/stream) Routes."""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from smart_parking.infrastructure.database.mysql_db import format_utc_iso, utc_now
from smart_parking.interfaces.http._compat import (
    APIRouter,
    Request,
    StreamingResponse,
    WebSocket,
    WebSocketDisconnect,
)
from smart_parking.interfaces.http.dependencies import get_container, get_current_user

router = APIRouter(prefix="/api", tags=["Realtime"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket channel pushing realtime updates immediately after MySQL transaction commits."""
    container = getattr(websocket.app.state, "container", None)
    if container is None:
        return
    try:
        token = websocket.cookies.get("access_token", "")
        container.auth_service.verify_token(token)
    except Exception:
        await websocket.close(code=4401)
        return
    await websocket.accept()

    queue = container.event_bus.subscribe_queue()
    try:
        await websocket.send_json({
            "event_type": "CONNECTED",
            "server_time": format_utc_iso(utc_now()),
            "payload": {"message": "Connected to Smart Parking Realtime Channel"},
        })
        while True:
            event = await queue.get()
            # Clients refresh role-filtered REST data; never broadcast other users' plates/bookings.
            await websocket.send_json({**event, "payload": {}})
    except WebSocketDisconnect:
        pass
    finally:
        container.event_bus.unsubscribe_queue(queue)


@router.get("/events/stream")
async def sse_events_stream(request: Request) -> StreamingResponse:
    """Server-Sent Events (SSE) stream pushing realtime updates after MySQL transaction commits."""
    container = get_container(request)
    get_current_user(request)
    queue = container.event_bus.subscribe_queue()

    async def _event_generator() -> AsyncIterator[str]:
        try:
            init_msg = json.dumps({
                "event_type": "CONNECTED",
                "server_time": format_utc_iso(utc_now()),
                "payload": {"channel": "sse"},
            })
            yield f"data: {init_msg}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps({**event, 'payload': {}})}\n\n"
                except asyncio.TimeoutError:
                    ping = json.dumps({
                        "event_type": "HEARTBEAT",
                        "server_time": format_utc_iso(utc_now()),
                    })
                    yield f"data: {ping}\n\n"
        finally:
            container.event_bus.unsubscribe_queue(queue)

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
