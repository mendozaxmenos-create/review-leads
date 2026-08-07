"""Envío de WhatsApp vía Twilio (plantillas Content API)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import settings


@dataclass
class TwilioSendResult:
    ok: bool
    dry_run: bool
    to: str
    sid: str | None = None
    error: str | None = None
    status: str | None = None


def normalize_whatsapp_number(phone: str) -> str | None:
    """Convierte teléfonos AR/Google a E.164 y prefijo whatsapp:."""
    raw = (phone or "").strip()
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    # Argentina: 549… (móvil con 9) o 54…
    if digits.startswith("54"):
        e164 = f"+{digits}"
    elif digits.startswith("0") and len(digits) >= 10:
        # 0261… → +54261…
        e164 = f"+54{digits.lstrip('0')}"
    elif len(digits) == 10:
        e164 = f"+54{digits}"
    else:
        e164 = f"+{digits}" if not raw.startswith("+") else f"+{digits}"
    return f"whatsapp:{e164}"


def extract_zone_from_reason(reason: str | None) -> str:
    """Usa el tag [Zona] que agrega la campaña Mendoza."""
    text = reason or ""
    m = re.match(r"\[([^\]]+)\]", text.strip())
    if m:
        return m.group(1).strip()
    return "Mendoza"


class TwilioWhatsAppService:
    def __init__(self) -> None:
        self.account_sid = settings.twilio_account_sid.strip()
        self.auth_token = settings.twilio_auth_token.strip()
        self.from_number = settings.twilio_whatsapp_from.strip()
        self.template_sid = settings.twilio_template_sid.strip()
        self.send_enabled = bool(settings.twilio_send_enabled)
        self.delay_seconds = float(settings.twilio_send_delay_seconds or 3.0)

    def configured_for_dry_run(self) -> bool:
        return True

    def configured_for_live(self) -> tuple[bool, str]:
        missing = []
        if not self.account_sid:
            missing.append("TWILIO_ACCOUNT_SID")
        if not self.auth_token:
            missing.append("TWILIO_AUTH_TOKEN")
        if not self.from_number:
            missing.append("TWILIO_WHATSAPP_FROM")
        if not self.template_sid:
            missing.append("TWILIO_TEMPLATE_SID")
        if missing:
            return False, "Faltan: " + ", ".join(missing)
        if not self.from_number.startswith("whatsapp:"):
            return False, "TWILIO_WHATSAPP_FROM debe empezar con whatsapp:"
        return True, "ok"

    def send_template(
        self,
        *,
        to_phone: str,
        place_name: str,
        zone: str,
        dry_run: bool | None = None,
    ) -> TwilioSendResult:
        to = normalize_whatsapp_number(to_phone)
        if not to:
            return TwilioSendResult(ok=False, dry_run=True, to="", error="teléfono inválido")

        is_dry = True if dry_run is None else dry_run
        if dry_run is None:
            is_dry = not self.send_enabled

        if is_dry:
            return TwilioSendResult(
                ok=True,
                dry_run=True,
                to=to,
                sid=None,
                status="dry_run",
            )

        ok, msg = self.configured_for_live()
        if not ok:
            return TwilioSendResult(ok=False, dry_run=False, to=to, error=msg)

        try:
            import json

            from twilio.rest import Client
        except ImportError:
            return TwilioSendResult(
                ok=False,
                dry_run=False,
                to=to,
                error="Instalá twilio: pip install twilio",
            )

        try:
            client = Client(self.account_sid, self.auth_token)
            # Content Template: variables {{1}}, {{2}}
            message = client.messages.create(
                from_=self.from_number,
                to=to,
                content_sid=self.template_sid,
                content_variables=json.dumps(
                    {
                        "1": (place_name or "hola")[:80],
                        "2": (zone or "Mendoza")[:60],
                    },
                    ensure_ascii=False,
                ),
            )
            return TwilioSendResult(
                ok=True,
                dry_run=False,
                to=to,
                sid=message.sid,
                status=message.status,
            )
        except Exception as exc:
            return TwilioSendResult(ok=False, dry_run=False, to=to, error=str(exc))
