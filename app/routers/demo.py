"""Demo pública: bot de reservas para que el prospecto pruebe (sin token)."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request
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


_PROD_DEMO_ORIGIN = "https://review-leads.onrender.com"
_TUNNEL_HINTS = ("trycloudflare.com", "ngrok-free.app", "ngrok.io", "loca.lt")


def public_demo_share_url() -> str | None:
    """URL para pegar en WhatsApp (origen público estable). Túneles → fallback Render."""
    base = (settings.demo_public_url or "").strip().rstrip("/")
    low = base.lower()
    if not base or any(h in low for h in _TUNNEL_HINTS) or "127.0.0.1" in low or "localhost" in low:
        base = _PROD_DEMO_ORIGIN
    return f"{base}/demo"


@router.get("/share-link")
async def demo_share_link() -> dict:
    """Para el dashboard: link listo para el pitch (si hay DEMO_PUBLIC_URL)."""
    url = public_demo_share_url()
    return {
        "url": url,
        "configured": bool(url),
        "token_required": False,
        "hint": (
            None
            if url
            else "Seteá DEMO_PUBLIC_URL=https://review-leads.onrender.com en el server"
        ),
    }


class DemoStartRequest(BaseModel):
    property_name: str | None = Field(default=None, max_length=80)


@router.post("/session")
async def start_demo_session(
    request: Request, body: DemoStartRequest | None = None
) -> dict:
    _rate_limit_session(request)
    name = (body.property_name if body else None) or None
    return demo_booking_bot.create_session(property_name=name)


@router.post("/chat")
async def demo_chat(body: DemoChatRequest) -> dict:
    try:
        return await demo_booking_bot.chat(body.session_id, body.message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/simulate-mp-payment")
async def simulate_mp_payment(body: DemoSessionRequest) -> dict:
    try:
        return demo_booking_bot.simulate_mp_payment(body.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/approve-transfer")
async def approve_transfer(body: DemoSessionRequest) -> dict:
    try:
        return demo_booking_bot.approve_transfer(body.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reject-transfer")
async def reject_transfer(body: DemoSessionRequest) -> dict:
    try:
        return demo_booking_bot.reject_transfer(body.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
