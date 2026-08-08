"""Crea plantilla WhatsApp Utility para avisos de Prioridad (dueño) y la envía a Meta."""
from __future__ import annotations

import sys

import httpx

from app.config import settings

FRIENDLY = "sofia_owner_prioridad_v1"
APPROVAL_NAME = "sofia_owner_prioridad_v1"

BODY = """SofIA · Prioridad (humano)
{{1}} necesita que le respondas.
Mensaje: {{2}}
Abrí el dashboard de campaña."""


def main() -> int:
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        print("Faltan credenciales Twilio", file=sys.stderr)
        return 1

    auth = (settings.twilio_account_sid, settings.twilio_auth_token)
    payload = {
        "friendly_name": FRIENDLY,
        "language": "es",
        "variables": {
            "1": "Cabañas Cerro Azul · Villa General Belgrano",
            "2": "Hola si",
        },
        "types": {"twilio/text": {"body": BODY}},
    }

    r = httpx.post(
        "https://content.twilio.com/v1/Content",
        json=payload,
        auth=auth,
        timeout=60,
    )
    print("create", r.status_code)
    print(r.text[:2000])
    r.raise_for_status()
    data = r.json()
    sid = data["sid"]

    ar = httpx.post(
        f"https://content.twilio.com/v1/Content/{sid}/ApprovalRequests/whatsapp",
        json={"name": APPROVAL_NAME, "category": "UTILITY"},
        auth=auth,
        timeout=60,
    )
    print("approval", ar.status_code)
    print(ar.text[:2000])
    ar.raise_for_status()
    print("ALERT_WHATSAPP_TEMPLATE_SID=" + sid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
