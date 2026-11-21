"""Pure source-to-preview assembly, shared by FastAPI and the isolated UI test server."""
from __future__ import annotations
import json
import re
from pathlib import Path

_DASHBOARD_DIR = Path(__file__).resolve().parent
_SRC_DIR = _DASHBOARD_DIR / "src"

_MODULE_ORDER = [
    _SRC_DIR / "shared" / "types" / "index.ts",
    _SRC_DIR / "shared" / "components" / "ui.tsx",
    _SRC_DIR / "services" / "api.client.ts",
    _SRC_DIR / "services" / "auth.service.ts",
    _SRC_DIR / "services" / "parking.service.ts",
    _SRC_DIR / "services" / "session.service.ts",
    _SRC_DIR / "services" / "review.service.ts",
    _SRC_DIR / "features" / "user-portal" / "driverRoutes.ts",
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
        "import.meta.env.VITE_API_BASE_URL",
        'undefined',
    )
    cleaned = cleaned.replace(
        "import.meta.env.VITE_WS_URL",
        'undefined',
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
        raw = mod_path.read_text(encoding="utf-8-sig")
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
    theme_css = (_SRC_DIR / "theme.css").read_text(encoding="utf-8-sig")

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Bãi đỗ PBL4</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script crossorigin src="https://unpkg.com/react@18.2.0/umd/react.production.min.js"></script>
  <script crossorigin src="https://unpkg.com/react-dom@18.2.0/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/@babel/standalone@7.24.7/babel.min.js"></script>
  <style>{theme_css}</style>
</head>
<body>
  <div id="root">
    <div class="loading-screen">
      Đang tải giao diện…
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

