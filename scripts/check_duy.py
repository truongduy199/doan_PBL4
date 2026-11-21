"""Read-only source/runtime checks. Never seed, reset a DB or send gate commands."""
from __future__ import annotations
import argparse
import ast
import importlib.util
import json
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "edge-server" / "src"))

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", action="store_true")
    parser.add_argument("--web-only", action="store_true")
    parser.add_argument("--network", action="store_true", help="Also try local configured database/broker TCP ports")
    args = parser.parse_args()
    failures = []
    count = 0
    for base in (ROOT / "edge-server" / "src", ROOT / "edge-server" / "scripts", ROOT / "scripts"):
        for path in base.rglob("*.py"):
            try:
                ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
                count += 1
            except (ValueError, SyntaxError) as exc:
                failures.append(f"Syntax: {path.relative_to(ROOT)}: {exc}")
    print(f"Parsed {count} Python source files")
    for path in (ROOT / "contracts").rglob("*.json"):
        try:
            json.loads(path.read_text(encoding="utf-8-sig"))
        except ValueError:
            failures.append(f"Invalid JSON: {path.relative_to(ROOT)}")
    if args.runtime:
        modules = ["fastapi", "uvicorn", "numpy", "cryptography", "bcrypt", "jwt", "pymysql"]
        if not args.web_only:
            modules += ["cv2", "paho.mqtt.client", "insightface", "onnxruntime", "ultralytics"]
        for module in modules:
            try:
                present = importlib.util.find_spec(module) is not None
            except ModuleNotFoundError:
                present = False
            print(f"{'OK' if present else 'MISSING'} module: {module}")
            if not present:
                failures.append(f"Install module {module}")
        from smart_parking.config.settings import Settings
        cfg = Settings()
        if cfg.mdns_enabled and importlib.util.find_spec("zeroconf") is None:
            failures.append("Install zeroconf for MDNS_ENABLED=true")
        if cfg.mqtt_enabled and (not cfg.mqtt_password or not cfg.device_api_key):
            failures.append("MQTT_PASSWORD and DEVICE_API_KEY must be configured")
        model_root = Path(cfg.face_model_root)
        if not model_root.is_absolute():
            model_root = ROOT / "edge-server" / model_root
        for suffix in (() if args.web_only else (f"models/{cfg.face_model_pack}", "addons")):
            if not list((model_root / suffix).glob("*.onnx")):
                failures.append(f"Missing local face model assets: {suffix}")
        if not (ROOT / "dashboard/dist/index.html").is_file():
            print("INFO: frontend dist is missing; CDN preview requires Internet")
        if args.network:
            for name, host, port in (("MySQL", cfg.mysql_host, cfg.mysql_port), ("MQTT", cfg.mqtt_host, cfg.mqtt_port)):
                try:
                    with socket.create_connection((host, port), timeout=2):
                        print(f"OK TCP {name}")
                except OSError:
                    failures.append(f"Cannot connect to {name} at configured address")
    for failure in failures:
        print(f"FAIL: {failure}")
    print(f"Result: {len(failures)} issue(s)")
    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
