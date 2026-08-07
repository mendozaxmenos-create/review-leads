"""Crea plantilla WhatsApp marketing Mendoza ($19.000) y la envía a Meta."""
from __future__ import annotations

import sys

import httpx

from app.config import settings

FRIENDLY = "sofia_mendoza_cabanas_v5"
APPROVAL_NAME = "sofia_mendoza_cabanas_v5"

BODY = """Hola, soy Gustavo de SofIA Desarrollos Informáticos.
Te escribo por {{1}} ({{2}}).
Tenemos un bot de reservas por WhatsApp a $19.000/mes: responde consultas y agenda sin que pierdan mensajes.
¿Te interesa que te cuente cómo funciona?
Si no querés más mensajes, respondé STOP."""


def main() -> int:
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        print("Faltan credenciales Twilio", file=sys.stderr)
        return 1

    auth = (settings.twilio_account_sid, settings.twilio_auth_token)
    payload = {
        "friendly_name": FRIENDLY,
        "language": "es",
        "variables": {"1": "Amalar Cabañas", "2": "Malargüe"},
        "types": {"twilio/text": {"body": BODY}},
    }

    r = httpx.post(
        "https://content.twilio.com/v1/Content",
        json=payload,
        auth=auth,
        timeout=60,
    )
    print("create", r.status_code)
    print(r.text[:1500])
    r.raise_for_status()
    data = r.json()
    sid = data["sid"]
    body_saved = data["types"]["twilio/text"]["body"]
    if "$19.000" not in body_saved:
        print("ERROR: precio mal guardado:", body_saved, file=sys.stderr)
        return 2

    ar = httpx.post(
        f"https://content.twilio.com/v1/Content/{sid}/ApprovalRequests/whatsapp",
        json={"name": APPROVAL_NAME, "category": "MARKETING"},
        auth=auth,
        timeout=60,
    )
    print("approval", ar.status_code)
    print(ar.text[:1500])
    ar.raise_for_status()
    print("HX", sid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
