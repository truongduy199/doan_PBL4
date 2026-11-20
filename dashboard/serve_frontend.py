"""
Frontend Development Server on Port 5173 for Smart Parking Dashboard & Web User Portal.
Compiles and serves the React + TypeScript + Tailwind SPA from `dashboard/src/` on http://127.0.0.1:5173
with full SPA History routing (/login, /user, /admin) connected live to FastAPI (http://127.0.0.1:8000).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import uvicorn

_DASHBOARD_DIR = Path(__file__).resolve().parent
_SRC_DIR = _DASHBOARD_DIR / "src"

_MODULE_ORDER = [
    _SRC_DIR / "shared" / "types" / "index.ts",
    _SRC_DIR / "services" / "api.client.ts",
    _SRC_DIR / "services" / "auth.service.ts",
    _SRC_DIR / "services" / "parking.service.ts",
    _SRC_DIR / "services" / "session.service.ts",
    _SRC_DIR / "services" / "review.service.ts",
    _SRC_DIR / "features" / "user-portal" / "FirstPersonDriverModal.tsx",
    _SRC_DIR / "features" / "auth" / "LoginPage.tsx",
    _SRC_DIR / "features" / "user-portal" / "UserBookingPortal.tsx",
    _SRC_DIR / "features" / "admin" / "AdminDashboardPage.tsx",
    _SRC_DIR / "app" / "App.tsx",
]


def _transform_ts_module(source: str) -> str:
    """Strip ES module imports/exports so all dashboard/src TypeScript/TSX modules run in one TSX compilation unit."""
    cleaned = re.sub(
        r"^\s*import\s+[\s\S]*?from\s+['\"][^'\"]+['\"];?\s*$",
        "",
        source,
        flags=re.MULTILINE,
    )
    cleaned = cleaned.replace(
        "(import.meta.env.VITE_API_BASE_URL as string | undefined)",
        '("http://127.0.0.1:8000" as string | undefined)',
    )
    cleaned = cleaned.replace(
        "(import.meta.env.VITE_WS_URL as string | undefined)",
        '("ws://127.0.0.1:8000/api/ws" as string | undefined)',
    )
    cleaned = re.sub(
        r"^\s*export\s+(interface|type|const|class|function)\b",
        r"\1",
        cleaned,
        flags=re.MULTILINE,
    )
    return cleaned


def build_spa_html() -> str:
    """Assemble the complete SPA HTML document from dashboard/src TypeScript/TSX files."""
    chunks: list[str] = []
    for mod_path in _MODULE_ORDER:
        raw = mod_path.read_text(encoding="utf-8")
        chunks.append(
            f"// === FILE: {mod_path.relative_to(_DASHBOARD_DIR).as_posix()} ===\n"
            + _transform_ts_module(raw)
        )

    router_prelude = """
const { useState, useEffect, useCallback, useRef, createContext, useContext } = React;

const RouterContext = createContext({
  path: window.location.pathname || "/login",
  navigate: (_to: string, _opts?: { replace?: boolean }) => {},
});

const BrowserRouter: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [path, setPath] = useState<string>(
    window.location.pathname === "/" || !window.location.pathname
      ? "/login"
      : window.location.pathname
  );

  useEffect(() => {
    const onPop = () => setPath(window.location.pathname || "/login");
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = useCallback((to: string, opts?: { replace?: boolean }) => {
    try {
      if (opts && opts.replace) {
        window.history.replaceState({}, "", to);
      } else {
        window.history.pushState({}, "", to);
      }
    } catch {
      // ignore file:// history pushState error
    }
    setPath(to);
  }, []);

  return (
    <RouterContext.Provider value={{ path, navigate }}>
      {children}
    </RouterContext.Provider>
  );
};

const useNavigate = () => useContext(RouterContext).navigate;

const Navigate: React.FC<{ to: string; replace?: boolean }> = ({ to, replace }) => {
  const { navigate } = useContext(RouterContext);
  useEffect(() => {
    navigate(to, { replace });
  }, [to, replace, navigate]);
  return null;
};

const Route: React.FC<{ path: string; element: React.ReactNode }> = ({ element }) => <>{element}</>;

const Routes: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { path } = useContext(RouterContext);
  const list = React.Children.toArray(children) as React.ReactElement[];
  for (const child of list) {
    if (child && child.props && child.props.path === path) {
      return <>{child.props.element}</>;
    }
  }
  const wildcard = list.find((c) => c && c.props && c.props.path === "*");
  return wildcard ? <>{wildcard.props.element}</> : null;
};
"""

    full_tsx_code = (
        router_prelude
        + "\n\n"
        + "\n\n".join(chunks)
        + "\n\nconst root = ReactDOM.createRoot(document.getElementById('root')!);\nroot.render(<App />);\n"
    )
    tsx_json_literal = json.dumps(full_tsx_code)

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Hệ Thống Bãi Đỗ Xe Thông Minh IoT - PBL4 (MySQL + FastAPI)</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script crossorigin src="https://unpkg.com/react@18.2.0/umd/react.production.min.js"></script>
  <script crossorigin src="https://unpkg.com/react-dom@18.2.0/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/@babel/standalone@7.24.7/babel.min.js"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@500;700;800&display=swap" rel="stylesheet">
  <style>
    body {{ font-family: 'Plus Jakarta Sans', sans-serif; }}
    .font-mono {{ font-family: 'JetBrains Mono', monospace; }}
  </style>
</head>
<body class="bg-slate-100 text-slate-800 antialiased">
  <div id="root">
    <div class="min-h-screen bg-slate-900 text-white flex items-center justify-center text-sm font-bold">
      ⏳ Đang khởi tạo giao diện Hệ Thống Bãi Đỗ Xe Thông Minh PBL4...
    </div>
  </div>

  <script>
    (function() {{
      try {{
        var rawTsx = {tsx_json_literal};
        var compiled = Babel.transform(rawTsx, {{
          filename: "app.tsx",
          presets: ["react", "typescript"]
        }}).code;
        var runner = new Function("React", "ReactDOM", compiled);
        runner(window.React, window.ReactDOM);
      }} catch (err) {{
        console.error("Frontend compilation/runtime error:", err);
        document.getElementById("root").innerHTML =
          '<div style="padding:24px;color:#991b1b;background:#fef2f2;font-family:monospace;">' +
          '<strong>Lỗi khởi tạo giao diện:</strong><pre>' + String(err && err.stack || err) + '</pre></div>';
      }}
    }})();
  </script>
</body>
</html>
"""


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
