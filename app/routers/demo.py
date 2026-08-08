"""Demo pública: bot de reservas para que el prospecto pruebe."""

from __future__ import annotations

import secrets
import time
from collections import defaultdict

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.config import settings
from app.services import demo_booking_bot

router = APIRouter(prefix="/api/demo", tags=["demo"])

# rate limit simple en memoria: sesiones nuevas por IP
_sessions_by_ip: dict[str, list[float]] = defaultdict(list)
_MAX_SESSIONS_PER_HOUR = 20


class DemoChatRequest(BaseModel):
    session_id: str = Field(min_length=8)
    message: str = Field(min_length=1, max_length=800)


class DemoSessionRequest(BaseModel):
    session_id: str = Field(min_length=8)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for") or ""
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def require_demo_token(
    k: str | None = None,
    x_demo_token: str | None = None,
) -> None:
    expected = (settings.demo_access_token or "").strip()
    if not expected:
        return  # local sin token = abierto (solo en tu PC)
    got = (x_demo_token or k or "").strip()
    if not got or not secrets.compare_digest(got, expected):
        raise HTTPException(
            status_code=401,
            detail="Demo protegida. Pedile el link a Gustavo de SofIA.",
        )


def _rate_limit_session(request: Request) -> None:
    ip = _client_ip(request)
    now = time.time()
    window = _sessions_by_ip[ip]
    _sessions_by_ip[ip] = [t for t in window if now - t < 3600]
    if len(_sessions_by_ip[ip]) >= _MAX_SESSIONS_PER_HOUR:
        raise HTTPException(
            status_code=429,
            detail="Demasiadas demos desde esta red. Probá más tarde.",
        )
    _sessions_by_ip[ip].append(now)


def public_demo_share_url() -> str | None:
    """URL para pegar en WhatsApp (origen público + token)."""
    base = (settings.demo_public_url or "").strip().rstrip("/")
    if not base:
        return None
    token = (settings.demo_access_token or "").strip()
    if token:
        return f"{base}/demo?k={token}"
    return f"{base}/demo"


@router.get("/share-link")
async def demo_share_link() -> dict:
    """Para el dashboard: link listo para el pitch (si hay DEMO_PUBLIC_URL)."""
    url = public_demo_share_url()
    return {
        "url": url,
        "configured": bool(url),
        "token_required": bool((settings.demo_access_token or "").strip()),
        "hint": (
            None
            if url
            else "Seteá DEMO_PUBLIC_URL (https://tu-app.onrender.com) y DEMO_ACCESS_TOKEN en .env"
        ),
    }


@router.post("/session")
async def start_demo_session(
    request: Request,
    k: str | None = Query(default=None),
    x_demo_token: str | None = Header(default=None, alias="X-Demo-Token"),
) -> dict:
    require_demo_token(k=k, x_demo_token=x_demo_token)
    _rate_limit_session(request)
    return demo_booking_bot.create_session()


@router.post("/chat")
async def demo_chat(
    body: DemoChatRequest,
    k: str | None = Query(default=None),
    x_demo_token: str | None = Header(default=None, alias="X-Demo-Token"),
) -> dict:
    require_demo_token(k=k, x_demo_token=x_demo_token)
    try:
        return await demo_booking_bot.chat(body.session_id, body.message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/simulate-mp-payment")
async def simulate_mp_payment(
    body: DemoSessionRequest,
    k: str | None = Query(default=None),
    x_demo_token: str | None = Header(default=None, alias="X-Demo-Token"),
) -> dict:
    require_demo_token(k=k, x_demo_token=x_demo_token)
    try:
        return demo_booking_bot.simulate_mp_payment(body.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/approve-transfer")
async def approve_transfer(
    body: DemoSessionRequest,
    k: str | None = Query(default=None),
    x_demo_token: str | None = Header(default=None, alias="X-Demo-Token"),
) -> dict:
    require_demo_token(k=k, x_demo_token=x_demo_token)
    try:
        return demo_booking_bot.approve_transfer(body.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reject-transfer")
async def reject_transfer(
    body: DemoSessionRequest,
    k: str | None = Query(default=None),
    x_demo_token: str | None = Header(default=None, alias="X-Demo-Token"),
) -> dict:
    require_demo_token(k=k, x_demo_token=x_demo_token)
    try:
        return demo_booking_bot.reject_transfer(body.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
