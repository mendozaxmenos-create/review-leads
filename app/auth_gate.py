"""Gates de acceso: demo pública abierta; dashboards SofIA con token opcional."""

from __future__ import annotations

import secrets

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse

from app.config import settings

DASHBOARD_PREFIXES = ("/campaign", "/admin", "/api/campaigns", "/api/admin")


def _expected_dashboard_token() -> str:
    return (settings.dashboard_access_token or "").strip()


def extract_dashboard_token(request: Request) -> str:
    return (
        request.headers.get("x-dashboard-token")
        or request.query_params.get("k")
        or ""
    ).strip()


def dashboard_token_ok(request: Request) -> bool:
    expected = _expected_dashboard_token()
    if not expected:
        return True
    got = extract_dashboard_token(request)
    return bool(got) and secrets.compare_digest(got, expected)


def path_needs_dashboard_token(path: str) -> bool:
    if path in ("/campaign", "/admin"):
        return True
    return path.startswith("/api/campaigns") or path.startswith("/api/admin")


def require_dashboard_token(request: Request) -> None:
    if dashboard_token_ok(request):
        return
    raise HTTPException(
        status_code=401,
        detail="Dashboard protegido. Abrí /campaign?k=TU_TOKEN o /admin?k=TU_TOKEN",
    )


def locked_dashboard_html() -> HTMLResponse:
    body = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SofIA — acceso</title>
  <style>
    body { font-family: system-ui, sans-serif; background: #0f1419; color: #e8eef4;
      display: grid; place-items: center; min-height: 100vh; margin: 0; padding: 1.5rem; }
    main { max-width: 28rem; }
    h1 { font-size: 1.25rem; margin: 0 0 .5rem; }
    p { color: #9aa8b5; line-height: 1.45; }
    code { color: #7ddea3; }
  </style>
</head>
<body>
  <main>
    <h1>Dashboard protegido</h1>
    <p>Abrí el link con tu clave, por ejemplo
      <code>/campaign?k=…</code> o <code>/admin?k=…</code>.</p>
  </main>
</body>
</html>"""
    return HTMLResponse(content=body, status_code=401)
