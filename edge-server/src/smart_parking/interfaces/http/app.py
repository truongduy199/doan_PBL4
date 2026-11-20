"""FastAPI Application Factory & Unified HTTP/Realtime Interface."""
from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlsplit

from smart_parking.domain.exceptions import DomainException
from smart_parking.infrastructure.database.mysql_db import format_utc_iso, utc_now
from smart_parking.interfaces.http._compat import (
    CORSMiddleware,
    FastAPI,
    HAS_FASTAPI,
    JSONResponse,
    Request,
    Response,
)
from smart_parking.interfaces.http.dependencies import AppContainer, build_container
from smart_parking.interfaces.http.routes import (
    admin,
    auth,
    bookings,
    health,
    realtime,
    reviews,
    slots,
)


def create_app(container: Optional[AppContainer] = None) -> FastAPI:
    """Create and configure the FastAPI application with all REST and Realtime routes."""
    app = FastAPI(
        title="Smart Parking PBL4 Edge API (MySQL/InnoDB)",
        version="0.2.0",
    )
    if container is not None:
        app.state.container = container

    if HAS_FASTAPI:
        app.add_middleware(
            CORSMiddleware,
            allow_origin_regex=r"https?://.*",
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.exception_handler(DomainException)
    async def domain_exception_handler(request: Request, exc: DomainException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "error": exc.reason_code,
                "reason_code": exc.reason_code,
                "message": exc.message,
                "details": exc.details,
                "server_time": format_utc_iso(utc_now()),
            },
        )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(slots.router)
    app.include_router(bookings.router)
    app.include_router(admin.router)
    app.include_router(realtime.router)
    app.include_router(reviews.router)

    if HAS_FASTAPI:
        from pathlib import Path
        from fastapi.responses import HTMLResponse  # type: ignore

        _repo_root = Path(__file__).resolve().parents[4]
        _serve_fe_path = _repo_root / "dashboard" / "serve_frontend.py"
        if _serve_fe_path.is_file():
            import importlib.util

            _spec = importlib.util.spec_from_file_location("serve_frontend", str(_serve_fe_path))
            if _spec and _spec.loader:
                _fe_mod = importlib.util.module_from_spec(_spec)
                _spec.loader.exec_module(_fe_mod)

                @app.get("/", response_class=HTMLResponse, include_in_schema=False)
                @app.get("/login", response_class=HTMLResponse, include_in_schema=False)
                @app.get("/user", response_class=HTMLResponse, include_in_schema=False)
                @app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
                async def _serve_unified_spa() -> HTMLResponse:
                    return HTMLResponse(content=_fe_mod.build_spa_html(), status_code=200)

    return app


app = create_app()


@dataclass
class ClientResponse:
    """Lightweight HTTP response wrapper used by LocalTestClient."""
    status_code: int
    _json_data: Any
    headers: Dict[str, str]
    cookies: Dict[str, str]

    def json(self) -> Any:
        return self._json_data


class LocalTestClient:
    """
    In-process synchronous HTTP test client for `app`.
    Uses Starlette/FastAPI TestClient when httpx+fastapi are installed,
    or dispatches directly through `app.routes` in offline environments.
    """

    def __init__(self, target_app: FastAPI) -> None:
        self.app = target_app
        self.cookies: Dict[str, str] = {}
        self._starlette_client: Any = None
        if HAS_FASTAPI:
            try:
                from fastapi.testclient import TestClient

                self._starlette_client = TestClient(target_app)
            except Exception:
                self._starlette_client = None

    def request(
        self,
        method: str,
        url: str,
        json: Any = None,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
    ) -> Any:
        if self._starlette_client is not None:
            kwargs: Dict[str, Any] = {}
            if json is not None:
                kwargs["json"] = json
            if headers is not None:
                kwargs["headers"] = headers
            if cookies is not None:
                kwargs["cookies"] = cookies
            return self._starlette_client.request(method, url, **kwargs)

        parsed = urlsplit(url)
        path = parsed.path.rstrip("/") or "/"
        raw_qs = parse_qs(parsed.query, keep_blank_values=True)
        query_params = {k: v[0] for k, v in raw_qs.items() if v}

        merged_cookies = dict(self.cookies)
        if cookies:
            merged_cookies.update(cookies)

        req = Request(
            method=method.upper(),
            url=url,
            headers=headers,
            cookies=merged_cookies,
            query_params=query_params,
            body_data=json,
            app=self.app,
        )
        resp = Response(status_code=200)

        for route in getattr(self.app, "routes", []):
            route_method = getattr(route, "method", None) or (
                list(getattr(route, "methods", []))[0] if getattr(route, "methods", None) else ""
            )
            if route_method != method.upper():
                continue

            regex = getattr(route, "regex", None) or getattr(route, "path_regex", None)
            if regex is None:
                continue
            m = regex.match(path)
            if not m:
                continue

            param_names = getattr(route, "param_names", None)
            if param_names is not None:
                path_kwargs = dict(zip(param_names, m.groups()))
            else:
                path_kwargs = m.groupdict()

            endpoint = route.endpoint
            sig = inspect.signature(endpoint)
            call_kwargs: Dict[str, Any] = {}
            for pname in sig.parameters:
                if pname == "request":
                    call_kwargs["request"] = req
                elif pname == "response":
                    call_kwargs["response"] = resp
                elif pname in path_kwargs:
                    call_kwargs[pname] = path_kwargs[pname]

            try:
                if inspect.iscoroutinefunction(endpoint):
                    coro = endpoint(**call_kwargs)
                    try:
                        while True:
                            coro.send(None)
                    except StopIteration as stop_exc:
                        payload = stop_exc.value
                    finally:
                        coro.close()
                else:
                    payload = endpoint(**call_kwargs)
                if isinstance(payload, JSONResponse):
                    return ClientResponse(
                        status_code=payload.status_code,
                        _json_data=payload.content,
                        headers=payload.headers,
                        cookies=payload.cookies,
                    )
                self.cookies.update(resp.cookies)
                return ClientResponse(
                    status_code=resp.status_code,
                    _json_data=payload,
                    headers=resp.headers,
                    cookies=dict(self.cookies),
                )
            except DomainException as exc:
                err_payload = {
                    "error": exc.reason_code,
                    "reason_code": exc.reason_code,
                    "message": exc.message,
                    "details": exc.details,
                    "server_time": format_utc_iso(utc_now()),
                }
                return ClientResponse(
                    status_code=exc.http_status,
                    _json_data=err_payload,
                    headers={},
                    cookies=dict(self.cookies),
                )

        return ClientResponse(
            status_code=404,
            _json_data={"error": "NOT_FOUND", "message": f"Route not found: {method} {path}"},
            headers={},
            cookies=dict(self.cookies),
        )

    def get(self, url: str, headers: Optional[Dict[str, str]] = None, cookies: Optional[Dict[str, str]] = None) -> ClientResponse:
        return self.request("GET", url, headers=headers, cookies=cookies)

    def post(
        self,
        url: str,
        json: Any = None,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
    ) -> ClientResponse:
        return self.request("POST", url, json=json, headers=headers, cookies=cookies)
