"""Crea plantilla WhatsApp marketing SofIA v6 (SIN precio) y la envía a Meta.

Objetivo: cold opener con dolor + demo, precio solo en el pitch post-reply.

Uso:
  .venv\\Scripts\\python -m scripts.create_wa_template_v6
"""
from __future__ import annotations

import sys

import httpx

from app.config import settings

FRIENDLY = "sofia_cabanas_v6_noprecio"
APPROVAL_NAME = "sofia_cabanas_v6_noprecio"

BODY = """Hola, soy Gustavo de SofIA.
Te escribo por {{1}} ({{2}}).
Armamos un bot de WhatsApp que atiende huéspedes 24/7: fechas, dudas y pre-reserva con seña, conectado a tu planilla o sistema.
¿Te paso una demo de 2 minutos para que lo veas?
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
    print(r.text[:2000])
    r.raise_for_status()
    data = r.json()
    sid = data["sid"]
    body_saved = data["types"]["twilio/text"]["body"]
    if "$19" in body_saved or "19.000" in body_saved:
        print("ERROR: no debería haber precio en v6:", body_saved, file=sys.stderr)
        return 2

    ar = httpx.post(
        f"https://content.twilio.com/v1/Content/{sid}/ApprovalRequests/whatsapp",
        json={"name": APPROVAL_NAME, "category": "MARKETING"},
        auth=auth,
        timeout=60,
    )
    print("approval", ar.status_code)
    print(ar.text[:2000])
    ar.raise_for_status()
    print("TWILIO_TEMPLATE_SID=" + sid)
    print("Cuando Meta apruebe, reemplazá TWILIO_TEMPLATE_SID en .env y poné CAMPAIGN_SEND_PAUSED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
