"""FastAPI compatibility layer: uses native FastAPI when installed, with an offline TestClient-ready shim."""
from __future__ import annotations

import inspect
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlsplit

try:
    from fastapi import (  # type: ignore
        APIRouter,
        Depends,
        FastAPI,
        Header,
        HTTPException,
        Query,
        Request,
        Response,
        WebSocket,
        WebSocketDisconnect,
    )
    from fastapi.middleware.cors import CORSMiddleware  # type: ignore
    from fastapi.responses import JSONResponse, StreamingResponse  # type: ignore

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

    class Depends:  # type: ignore
        def __init__(self, dependency: Optional[Callable[..., Any]] = None) -> None:
            self.dependency = dependency

    def Header(default: Any = None, alias: Optional[str] = None, **kwargs: Any) -> Any:  # type: ignore
        return default

    def Query(default: Any = None, **kwargs: Any) -> Any:  # type: ignore
        return default

    class HTTPException(Exception):  # type: ignore
        def __init__(self, status_code: int, detail: Any = None) -> None:
            super().__init__(str(detail))
            self.status_code = status_code
            self.detail = detail

    class Request:  # type: ignore
        def __init__(
            self,
            method: str = "GET",
            url: str = "/",
            headers: Optional[Dict[str, str]] = None,
            cookies: Optional[Dict[str, str]] = None,
            query_params: Optional[Dict[str, str]] = None,
            body_data: Any = None,
            app: Any = None,
        ) -> None:
            self.method = method.upper()
            self.url = url
            self.headers: Dict[str, str] = {k.lower(): v for k, v in (headers or {}).items()}
            self.cookies: Dict[str, str] = dict(cookies or {})
            self.query_params: Dict[str, str] = dict(query_params or {})
            self._body_data = body_data
            self.app = app

        async def json(self) -> Any:
            if isinstance(self._body_data, (dict, list)):
                return self._body_data
            if isinstance(self._body_data, (bytes, bytearray)):
                return json.loads(self._body_data.decode("utf-8"))
            if isinstance(self._body_data, str):
                return json.loads(self._body_data)
            return {}

    class Response:  # type: ignore
        def __init__(
            self,
            content: Any = None,
            status_code: int = 200,
            headers: Optional[Dict[str, str]] = None,
            media_type: Optional[str] = None,
        ) -> None:
            self.content = content
            self.status_code = status_code
            self.headers: Dict[str, str] = dict(headers or {})
            self.media_type = media_type
            self.cookies: Dict[str, str] = {}

        def set_cookie(self, key: str, value: str = "", **kwargs: Any) -> None:
            self.cookies[key] = value

        def delete_cookie(self, key: str, **kwargs: Any) -> None:
            self.cookies.pop(key, None)

    class JSONResponse(Response):  # type: ignore
        def __init__(
            self,
            content: Any,
            status_code: int = 200,
            headers: Optional[Dict[str, str]] = None,
        ) -> None:
            super().__init__(
                content=content,
                status_code=status_code,
                headers=headers,
                media_type="application/json",
            )

    class StreamingResponse(Response):  # type: ignore
        def __init__(
            self,
            content: Any,
            status_code: int = 200,
            headers: Optional[Dict[str, str]] = None,
            media_type: Optional[str] = None,
        ) -> None:
            super().__init__(
                content=content,
                status_code=status_code,
                headers=headers,
                media_type=media_type,
            )

    class WebSocket:  # type: ignore
        def __init__(self, app: Any = None) -> None:
            self.app = app
            self.accepted = False
            self.sent_messages: List[Any] = []

        async def accept(self) -> None:
            self.accepted = True

        async def send_json(self, data: Any) -> None:
            self.sent_messages.append(data)

        async def receive_text(self) -> str:
            raise WebSocketDisconnect()

    class WebSocketDisconnect(Exception):  # type: ignore
        pass

    class CORSMiddleware:  # type: ignore
        pass

    @dataclass
    class _RouteDef:
        method: str
        path_pattern: str
        regex: re.Pattern
        param_names: List[str]
        endpoint: Callable[..., Any]

    def _compile_path(path: str) -> Tuple[re.Pattern, List[str]]:
        param_names: List[str] = []
        pattern = "^"
        pos = 0
        for m in re.finditer(r"\{([a-zA-Z0-9_]+)\}", path):
            pattern += re.escape(path[pos : m.start()])
            param_names.append(m.group(1))
            pattern += r"([^/]+)"
            pos = m.end()
        pattern += re.escape(path[pos:]) + "/?$"
        return re.compile(pattern), param_names

    class APIRouter:  # type: ignore
        def __init__(self, prefix: str = "", tags: Optional[List[str]] = None) -> None:
            self.prefix = prefix.rstrip("/")
            self.tags = tags or []
            self.routes: List[_RouteDef] = []
            self.ws_routes: List[_RouteDef] = []

        def _add(self, method: str, path: str, endpoint: Callable[..., Any]) -> Callable[..., Any]:
            full_path = f"{self.prefix}/{path.lstrip('/')}".rstrip("/") or "/"
            regex, params = _compile_path(full_path)
            self.routes.append(_RouteDef(method.upper(), full_path, regex, params, endpoint))
            return endpoint

        def get(self, path: str, **kwargs: Any) -> Callable[..., Any]:
            return lambda fn: self._add("GET", path, fn)

        def post(self, path: str, **kwargs: Any) -> Callable[..., Any]:
            return lambda fn: self._add("POST", path, fn)

        def put(self, path: str, **kwargs: Any) -> Callable[..., Any]:
            return lambda fn: self._add("PUT", path, fn)

        def delete(self, path: str, **kwargs: Any) -> Callable[..., Any]:
            return lambda fn: self._add("DELETE", path, fn)

        def websocket(self, path: str, **kwargs: Any) -> Callable[..., Any]:
            def _decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
                full_path = f"{self.prefix}/{path.lstrip('/')}".rstrip("/") or "/"
                regex, params = _compile_path(full_path)
                self.ws_routes.append(_RouteDef("WS", full_path, regex, params, fn))
                return fn
            return _decorator

    class FastAPI(APIRouter):  # type: ignore
        def __init__(self, title: str = "FastAPI", version: str = "0.1.0", **kwargs: Any) -> None:
            super().__init__(prefix="")
            self.title = title
            self.version = version
            self.state = type("AppState", (), {})()
            self._exception_handlers: Dict[Any, Callable[..., Any]] = {}

        def add_middleware(self, middleware_class: Any, **kwargs: Any) -> None:
            pass

        def exception_handler(self, exc_class: Any) -> Callable[..., Any]:
            def _register(fn: Callable[..., Any]) -> Callable[..., Any]:
                self._exception_handlers[exc_class] = fn
                return fn
            return _register

        def include_router(self, router: APIRouter, prefix: str = "", **kwargs: Any) -> None:
            pfx = prefix.rstrip("/")
            for r in router.routes:
                full = f"{pfx}{r.path_pattern}" if pfx else r.path_pattern
                regex, params = _compile_path(full)
                self.routes.append(_RouteDef(r.method, full, regex, params, r.endpoint))
            for wr in router.ws_routes:
                full = f"{pfx}{wr.path_pattern}" if pfx else wr.path_pattern
                regex, params = _compile_path(full)
                self.ws_routes.append(_RouteDef("WS", full, regex, params, wr.endpoint))
