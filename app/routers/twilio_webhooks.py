"""Webhooks Twilio WhatsApp: inbound + status."""

from __future__ import annotations

import re

from fastapi import APIRouter, Form, Request, Response

from app.db.store import get_store
from app.services.mendoza_campaign import CAMPAIGN_ID, CAMPAIGN_TAG

router = APIRouter(prefix="/api/twilio", tags=["twilio"])


def _digits(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


@router.post("/whatsapp/inbound")
async def whatsapp_inbound(
    request: Request,
    From: str = Form(default=""),
    Body: str = Form(default=""),
    MessageSid: str = Form(default=""),
) -> Response:
    """
    Configurar en Twilio (Sandbox o sender):
    When a message comes in → https://<tu-host>/api/twilio/whatsapp/inbound

    No responde por Twilio (ahorra costo). Marca CRM responded y guarda el mensaje.
    Seguí la charla desde tu WhatsApp personal (handoff).
    """
    store = get_store()
    store.init()

    from_raw = From or ""
    body = (Body or "").strip()
    sid = MessageSid or None
    digits = _digits(from_raw)

    lead_row = store.find_lead_by_phone_digits(digits)
    place_id = lead_row["place_id"] if lead_row else None

    store.log_campaign_message(
        campaign=CAMPAIGN_ID,
        place_id=place_id,
        phone=from_raw.replace("whatsapp:", "") if from_raw else digits,
        direction="inbound",
        body=body,
        twilio_sid=sid,
    )

    if lead_row and lead_row.get("status") in ("new", "contacted"):
        note = (lead_row.get("notes") or "").strip()
        reply_note = f"Respondió WhatsApp: {body[:120]}"
        store.update_saved_lead(
            lead_row["id"],
            status="responded",
            notes=(note + (" | " if note else "") + reply_note),
        )

    # Empty TwiML = no auto-reply (no cobro de respuesta automática)
    return Response(
        content="<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response></Response>",
        media_type="application/xml",
    )


@router.post("/whatsapp/status")
async def whatsapp_status(
    MessageSid: str = Form(default=""),
    MessageStatus: str = Form(default=""),
    To: str = Form(default=""),
) -> dict[str, str]:
    """Status callback opcional (queued/sent/delivered/failed)."""
    # Por ahora solo ack; se puede enriquecer el log de campaign_sends
    return {"ok": "true", "sid": MessageSid, "status": MessageStatus}
