"""Bounded MQTT ingress; network callbacks never execute AI or database work."""
from __future__ import annotations
import json
import logging
import queue
import threading
from typing import Any, Dict
logger = logging.getLogger(__name__)

class MqttGateBridge:
    def __init__(self, workflow_service: Any, broker_host: str = "127.0.0.1", broker_port: int = 1883,
                 username: str = "", password: str = "") -> None:
        self.workflow_service = workflow_service
        self.broker_host, self.broker_port = broker_host, broker_port
        self.username, self.password = username, password
        self._client: Any = None
        self._connected = False
        self._queue: queue.Queue = queue.Queue(maxsize=256)
        self._stop = threading.Event()
        self._worker: Any = None
        self.last_error: str | None = None
        workflow_service.set_mqtt_publisher(self.publish_json)

    def status(self) -> Dict[str, Any]:
        return {"enabled": True, "connected": self._connected,
                "queued_messages": self._queue.qsize(), "last_error": self.last_error}

    def publish_json(self, topic: str, payload: Dict[str, Any]) -> None:
        if self._client is None or not self._connected:
            raise RuntimeError("MQTT_DISCONNECTED")
        result = self._client.publish(topic, json.dumps(payload, ensure_ascii=False), qos=1, retain=False)
        if result.rc != 0:
            raise RuntimeError(f"MQTT_PUBLISH_FAILED:{result.rc}")

    def _consume(self) -> None:
        while not self._stop.is_set():
            try:
                topic, payload = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            try:
                self.workflow_service.handle_mqtt_message(topic, payload)
                if topic in ("parking/gates/IN/detected", "parking/gates/OUT/detected"):
                    self.publish_json(f"parking/devices/{payload['device_id']}/event_ack",
                                      {"boot_id": payload["boot_id"], "sequence": payload["sequence"], "accepted": True})
            except Exception as exc:
                self.last_error = str(getattr(exc, "reason_code", type(exc).__name__))
                logger.exception("Rejected MQTT message on %s", topic)
                if getattr(exc, "http_status", 500) < 500 and payload.get("device_id") == self.workflow_service.settings.controller_device_id:
                    try:
                        self.publish_json(f"parking/devices/{payload['device_id']}/event_ack",
                                          {"boot_id": payload.get("boot_id"), "sequence": payload.get("sequence"),
                                           "accepted": False, "reason_code": self.last_error})
                    except Exception:
                        pass
            finally:
                self._queue.task_done()

    def start_background(self) -> bool:
        if self._client is not None:
            return True
        try:
            import paho.mqtt.client as mqtt
            client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                                 client_id="pbl4-edge-backend", clean_session=True)
            if not self.username or not self.password:
                raise ValueError("MQTT_CREDENTIALS_REQUIRED")
            client.username_pw_set(self.username, self.password)
            client.max_queued_messages_set(32)
            client.reconnect_delay_set(min_delay=1, max_delay=15)
            def connected(c: Any, _u: Any, _f: Any, reason: Any, _p: Any) -> None:
                self._connected = reason == 0
                if self._connected:
                    self.last_error = None
                    for topic in ("parking/gates/IN/detected", "parking/gates/OUT/detected",
                                  "parking/slots/snapshot", "parking/devices/+/ack", "parking/devices/+/status"):
                        c.subscribe(topic, qos=1)
            def disconnected(_c: Any, _u: Any, _f: Any, _r: Any, _p: Any) -> None:
                self._connected = False
            def message(_c: Any, _u: Any, msg: Any) -> None:
                if msg.retain or len(msg.payload) > 16384:
                    return
                try:
                    body = json.loads(msg.payload.decode("utf-8"))
                    if not isinstance(body, dict):
                        raise ValueError("Payload must be an object")
                    self._queue.put_nowait((msg.topic, body))
                except (ValueError, UnicodeError, queue.Full):
                    self.last_error = "INVALID_OR_OVERFLOW_MQTT_MESSAGE"
            client.on_connect, client.on_disconnect, client.on_message = connected, disconnected, message
            self._client = client
            self._stop.clear()
            self._worker = threading.Thread(target=self._consume, name="pbl4-mqtt-ingress", daemon=True)
            self._worker.start()
            client.connect_async(self.broker_host, self.broker_port, keepalive=20)
            client.loop_start()
            return True
        except Exception as exc:
            self.last_error = str(exc)
            logger.error("MQTT startup failed: %s", exc)
            self.stop()
            return False

    def stop(self) -> None:
        self._stop.set()
        if self._client is not None:
            self._client.disconnect()
            self._client.loop_stop()
            self._client = None
        self._connected = False
        if self._worker is not None:
            self._worker.join(timeout=3)
            self._worker = None
