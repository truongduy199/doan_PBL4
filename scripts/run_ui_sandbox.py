"""Isolated UI integration server using real services/repos and an in-memory test DB.

This is NOT the production FastAPI/MySQL server. It never connects to devices,
changes the demo DB or runs AI inference. A visible banner identifies the test UI.
"""
from __future__ import annotations
import argparse
import json
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "edge-server/src", ROOT / "edge-server/tests", ROOT / "edge-server", ROOT / "dashboard"):
    sys.path.insert(0, str(path))

from fakes.fake_mysql_db import SandboxMySQLTestDatabase
from scripts.seed_demo_data import seed_demo_data
from smart_parking.config.settings import Settings
from smart_parking.interfaces.http.app import LocalTestClient, create_app
from smart_parking.interfaces.http.dependencies import build_container
from spa import build_spa_html


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    settings = Settings(mysql_database="pbl4_ui_memory_test", mqtt_enabled=False, mdns_enabled=False,
                        slot_stale_seconds=86400, jwt_secret_key="ui-sandbox-only-not-production",
                        embedding_secret_key="MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
                        demo_admin_password="Admin@123", demo_user_password="Viet@123")
    db = SandboxMySQLTestDatabase(settings)
    container = build_container(settings=settings, db=db)
    seed_demo_data(uow=container.uow, cipher=container.cipher, settings=settings,
                   with_test_fixtures=True, init_slots_free=True)
    app = create_app(container=container, enable_background_worker=False)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.dispatch()

        def do_POST(self):
            self.dispatch()

        def dispatch(self):
            if self.path.startswith(("/api/ws", "/api/events/stream")):
                self.send_error(501, "Realtime transport is not part of this isolated test server")
                return
            if not self.path.startswith(("/api/", "/health")):
                if self.command != "GET":
                    self.send_error(405)
                    return
                html = build_spa_html().replace("<body>", '<body data-ui-sandbox="true">')
                self.reply(200, html.encode("utf-8"), "text/html; charset=utf-8")
                return
            try:
                cookies = SimpleCookie(self.headers.get("Cookie", ""))
                client = LocalTestClient(app)
                length = int(self.headers.get("Content-Length", "0"))
                if length > 1024 * 1024:
                    self.send_error(413)
                    return
                payload = self.rfile.read(length) if length else None
                result = client.request(self.command, self.path, content=payload,
                                        headers=dict(self.headers), cookies={k: v.value for k, v in cookies.items()})
                body = json.dumps(result.json(), ensure_ascii=False).encode("utf-8")
                self.reply(result.status_code, body, "application/json; charset=utf-8", result.cookies)
            except Exception as exc:
                self.reply(500, json.dumps({"message": str(exc), "reason_code": "SANDBOX_ERROR"}).encode(), "application/json")

        def reply(self, status, body, content_type, cookies=None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for key, value in (cookies or {}).items():
                if key == "access_token":
                    self.send_header("Set-Cookie", f"{key}={value}; Path=/; HttpOnly; SameSite=Lax" + ("; Max-Age=0" if not value else ""))
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer(("127.0.0.1", args.port), Handler)
    print(f"ISOLATED UI TEST SERVER http://127.0.0.1:{args.port}/login", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        db._raw_conn.close()


if __name__ == "__main__":
    main()
