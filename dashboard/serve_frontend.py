"""Optional FastAPI dev server; production serves the Vite build when present."""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import uvicorn
from pathlib import Path
from spa import build_spa_html

_DASHBOARD_DIR = Path(__file__).resolve().parent

frontend_app = FastAPI(title="Smart Parking Frontend Dev Server (Port 5173)")


@frontend_app.get("/{full_path:path}", response_class=HTMLResponse)
async def serve_spa(request: Request, full_path: str) -> HTMLResponse:
    return HTMLResponse(content=build_spa_html(), status_code=200)


if __name__ == "__main__":
    try:
        (_DASHBOARD_DIR / "preview.html").write_text(build_spa_html(), encoding="utf-8")
    except Exception:
        pass
    uvicorn.run(frontend_app, host="127.0.0.1", port=5173, log_level="info")
