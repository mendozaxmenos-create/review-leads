"""Demo pública: bot de reservas para que el prospecto pruebe."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import demo_booking_bot

router = APIRouter(prefix="/api/demo", tags=["demo"])


class DemoChatRequest(BaseModel):
    session_id: str = Field(min_length=8)
    message: str = Field(min_length=1, max_length=800)


@router.post("/session")
async def start_demo_session() -> dict:
    return demo_booking_bot.create_session()


@router.post("/chat")
async def demo_chat(body: DemoChatRequest) -> dict:
    try:
        return await demo_booking_bot.chat(body.session_id, body.message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
