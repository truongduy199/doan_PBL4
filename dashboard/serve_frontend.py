"""Optional FastAPI dev server; production serves the Vite build when present."""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import uvicorn
from spa import build_spa_html

frontend_app = FastAPI(title="Smart Parking Frontend Dev Server (Port 5173)")


@frontend_app.get("/{full_path:path}", response_class=HTMLResponse)
async def serve_spa(request: Request, full_path: str) -> HTMLResponse:
    return HTMLResponse(content=build_spa_html(), status_code=200)


if __name__ == "__main__":
    uvicorn.run(frontend_app, host="127.0.0.1", port=5173, log_level="info")
