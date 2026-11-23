"""Capture real ESP JPEGs with optional AI, without database writes or gate commands.

Temporarily serves the existing device HTTP routes on port 8000. Refuses to
replace a running backend. Frames stay in RAM and are discarded on exit.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import socket
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "edge-server/src"))

import paho.mqtt.client as mqtt
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from types import SimpleNamespace

from smart_parking.application.services.gate_workflow_service import GateTurnContext, GateWorkflowService
from smart_parking.config.settings import Settings
from smart_parking.domain.exceptions import DomainException
from smart_parking.infrastructure.database.mysql_db import utc_now
from smart_parking.interfaces.http.routes.device import router


def load_ai(cfg):
    from smart_parking.ai.face.insightface_adapter import InsightFaceAdapter
    from smart_parking.ai.face.pipeline import FacePipeline
    from smart_parking.ai.plate.pipeline import PlatePipeline
    from license_plate_yolo_numpy.pipeline import DEFAULT_YOLO_WEIGHTS, DEFAULT_OCR_WEIGHTS

    root = Path(cfg.face_model_root)
    if not root.is_absolute():
        root = ROOT / "edge-server" / root
    if len(list((root / "models" / cfg.face_model_pack).glob("*.onnx"))) < 5:
        raise RuntimeError("Local Buffalo-L assets are missing; no models will be downloaded.")
    for weights in (DEFAULT_YOLO_WEIGHTS, DEFAULT_OCR_WEIGHTS):
        if not Path(weights).is_file():
            raise RuntimeError("Local plate weights are missing; no models will be downloaded.")
    adapter = InsightFaceAdapter(model_root=root, model_pack=cfg.face_model_pack, provider=cfg.face_provider)
    if not adapter.initialize():
        raise RuntimeError("InsightFace initialization failed.")
    plate = PlatePipeline()
    plate._ensure_reader()
    print("AI_MODELS_READY " + json.dumps({"face_provider": adapter.runtime_provider,
          "local_liveness_asset": (root / "addons/liveness.onnx").is_file(), "plate_reader": True}), flush=True)
    return plate, FacePipeline(adapter=adapter)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ai", action="store_true", help="Run real AI on the captured frames; gates and database stay disabled")
    parser.add_argument("--models-only", action="store_true", help="Load local AI models and exit without camera requests")
    args = parser.parse_args()
    cfg = Settings()
    models = load_ai(cfg) if args.ai or args.models_only else None
    if args.models_only:
        return 0
    if not cfg.device_api_key or not cfg.mqtt_password:
        raise SystemExit("Configure DEVICE_API_KEY and MQTT_PASSWORD first.")
    with socket.socket() as probe:
        try:
            probe.bind(("0.0.0.0", cfg.http_port))
        except OSError:
            raise SystemExit("HTTP port is occupied; this check will not replace the backend.")

    def prohibit_publish(*_args):
        raise RuntimeError("Gate publishing is disabled in this capture check.")

    workflow = GateWorkflowService(gate_data_service=None, settings=cfg, mqtt_publish_fn=prohibit_publish)
    app = FastAPI(title="Temporary camera capture diagnostic")
    app.state.container = SimpleNamespace(settings=cfg, gate_workflow_service=workflow)
    app.include_router(router)
    received = {}
    frames_ready = threading.Event()
    ingest = workflow.ingest_device_image

    def ingest_without_inference(**kwargs):
        result = ingest(**kwargs, auto_evaluate_when_ready=False)
        camera = result["camera_id"]
        received[camera] = {"device_id": result["device_id"], "bytes": len(kwargs["image_bytes"]),
                            "resolution": result["resolution"], "accepted": result["accepted"]}
        print("JPEG_RECEIVED " + json.dumps({"camera": camera, **received[camera]}), flush=True)
        if len(received) == 2:
            frames_ready.set()
        return result

    workflow.ingest_device_image = ingest_without_inference

    @app.exception_handler(DomainException)
    async def domain_error(_request, exc):
        print("IMAGE_REJECTED " + exc.reason_code, flush=True)
        return JSONResponse(status_code=exc.http_status,
                            content={"error": exc.reason_code, "message": exc.message})

    server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=cfg.http_port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    connected = threading.Event()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="pbl4-capture-check-" + uuid.uuid4().hex[:8])
    client.username_pw_set(cfg.mqtt_username, cfg.mqtt_password)

    def on_connect(c, _u, _flags, reason, _properties):
        if not reason.is_failure:
            connected.set()

    client.on_connect = on_connect
    try:
        thread.start()
        for _ in range(100):
            if server.started:
                break
            if not thread.is_alive():
                raise RuntimeError("Diagnostic HTTP server did not start.")
            time.sleep(0.1)
        if not server.started:
            raise RuntimeError("Diagnostic HTTP startup timeout.")
        client.connect(cfg.mqtt_host, cfg.mqtt_port, 20)
        client.loop_start()
        if not connected.wait(5):
            raise RuntimeError("MQTT authentication failed.")
        print("HTTP_READY: waiting 35 seconds for ESP clock synchronization; automatic decisions/DB/gates disabled.", flush=True)
        time.sleep(35)
        now = utc_now()
        event = "capture-" + uuid.uuid4().hex[:20]
        workflow._turns[event] = GateTurnContext(
            event_id=event, gate_id="IN", device_id=cfg.controller_device_id,
            boot_id="capture-diagnostic", sequence=1, roi="ROI_IN", created_at=now,
            state="CAPTURING", capture_started_at=now)
        workflow._active_event_id = event
        for camera in ("plate", "face"):
            payload = {"event_id": event, "gate_id": "IN", "roi": "ROI_IN",
                       "frame_id": f"req-{camera}-{event}",
                       "expires_at_ms": int(now.timestamp() * 1000) + 5000}
            info = client.publish(f"parking/cameras/{camera}/capture", json.dumps(payload), qos=1, retain=False)
            info.wait_for_publish(timeout=3)
            print("CAPTURE_SENT " + camera, flush=True)
        success = frames_ready.wait(12)
        print("CAPTURE_RESULT " + json.dumps({"success": success, "cameras": received}), flush=True)
        if success and models:
            turn = workflow._turns[event]
            plate, face = models
            plate_result = plate.process_frame(turn.plate_frames[0], roi=cfg.gate_rois[("plate", "IN")])
            print("PLATE_AI " + json.dumps(plate_result.to_dict(), ensure_ascii=False), flush=True)
            face_result = face.process_frame(turn.face_frames[0], require_liveness=True,
                                            roi=cfg.gate_rois[("face", "IN")])
            print("FACE_AI " + json.dumps({"ok": face_result.ok, "reason_code": face_result.reason_code,
                  "message": face_result.message, "quality_score": face_result.quality_score,
                  "liveness_status": face_result.liveness_status, "liveness_score": face_result.liveness_score,
                  "embedding_available": face_result.embedding is not None}, ensure_ascii=False), flush=True)
            print("Identity comparison was not performed; no reference driver template was supplied.", flush=True)
            return 0 if plate_result.ok and face_result.ok else 2
        return 0 if success else 1
    finally:
        client.disconnect()
        client.loop_stop()
        server.should_exit = True
        thread.join(timeout=5)
        workflow._turns.clear()
        workflow._camera_images.clear()
        print("Diagnostic stopped; RAM frames released.", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
