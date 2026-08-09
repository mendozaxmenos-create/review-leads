"""Avisos al dueño cuando un lead humano entra a Prioridad."""

from __future__ import annotations

import json
import logging
import smtplib
import time
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)


def should_alert_human_reply(inbound_bodies_oldest_first: list[str | None]) -> bool:
    """True solo al pasar a needs_you (evita spam en cada msg humano siguiente)."""
    from app.services.reply_classify import classify_inbound_body, classify_inbound_thread

    if not inbound_bodies_oldest_first:
        return False
    # Opt-out: no avisar aunque después digan «gracias» u otro texto corto
    kinds = [classify_inbound_body(b) for b in inbound_bodies_oldest_first]
    if "stop" in kinds:
        return False
    now = classify_inbound_thread(inbound_bodies_oldest_first)
    if not now.get("needs_you"):
        return False
    if len(inbound_bodies_oldest_first) == 1:
        return True
    prior = classify_inbound_thread(inbound_bodies_oldest_first[:-1])
    return not prior.get("needs_you")


def _normalize_wa(to: str) -> str | None:
    raw = (to or "").strip()
    if not raw:
        return None
    if raw.startswith("whatsapp:"):
        return raw
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return None
    if not digits.startswith("54"):
        digits = "54" + digits.lstrip("0")
    return f"whatsapp:+{digits}"


def build_alert_text(
    *,
    place_name: str,
    zone: str,
    base: str,
    phone: str,
    body: str,
    thread_label: str,
) -> str:
    snippet = (body or "").strip().replace("\n", " ")[:900]
    dash = (settings.alert_dashboard_url or "http://127.0.0.1:8000/campaign").rstrip("/")
    return (
        f"SofIA · Prioridad (humano)\n"
        f"{place_name or 'Lead'}"
        + (f" · {zone}" if zone else "")
        + (f" · {base}" if base else "")
        + "\n"
        f"{thread_label}\n"
        f"«{snippet}»\n"
        f"Tel: {phone}\n"
        f"Dashboard: {dash}"
    )


def _alert_headline(place_name: str, zone: str, base: str) -> str:
    parts = [p for p in [(place_name or "").strip(), (zone or "").strip(), (base or "").strip()] if p]
    return (" · ".join(parts) or "Lead")[:80]


def _alert_snippet(body: str) -> str:
    # Content/WhatsApp vars ~1024; dejamos margen para no romper la plantilla
    return (body or "").strip().replace("\n", " ")[:900] or "(sin texto)"


def _wait_delivery(client, sid: str, *, attempts: int = 6, delay: float = 1.0) -> tuple[str, int | None, str | None]:
    """Poll corto para detectar undelivered (ej. 63016) en el test/aviso."""
    status = ""
    err_code: int | None = None
    err_msg: str | None = None
    for _ in range(max(1, attempts)):
        time.sleep(delay)
        msg = client.messages(sid).fetch()
        status = (msg.status or "").lower()
        err_code = msg.error_code
        err_msg = msg.error_message
        if status in ("delivered", "read", "failed", "undelivered"):
            break
    return status, err_code, err_msg


def send_alert_whatsapp(
    text: str,
    *,
    place_name: str = "",
    zone: str = "",
    base: str = "",
    body: str = "",
    wait_delivery: bool = False,
) -> tuple[bool, str]:
    to = _normalize_wa(settings.alert_whatsapp_to)
    if not to:
        return False, "ALERT_WHATSAPP_TO vacío"
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        return False, "Faltan credenciales Twilio"
    from_number = (settings.twilio_whatsapp_from or "").strip()
    if not from_number.startswith("whatsapp:"):
        return False, "TWILIO_WHATSAPP_FROM inválido"
    try:
        from twilio.rest import Client
    except ImportError:
        return False, "Instalá twilio"

    template_sid = (settings.alert_whatsapp_template_sid or "").strip()
    try:
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        if template_sid:
            headline = _alert_headline(place_name, zone, base)
            snippet = _alert_snippet(body)
            msg = client.messages.create(
                from_=from_number,
                to=to,
                content_sid=template_sid,
                content_variables=json.dumps(
                    {"1": headline, "2": snippet},
                    ensure_ascii=False,
                ),
            )
            mode = "template"
        else:
            msg = client.messages.create(from_=from_number, to=to, body=text[:1500])
            mode = "freeform"

        sid = msg.sid or "ok"
        detail = f"{mode}:{sid}"
        if wait_delivery and msg.sid:
            status, err_code, err_msg = _wait_delivery(client, msg.sid)
            detail = f"{mode}:{sid}:{status}"
            if status in ("failed", "undelivered") or err_code:
                return False, f"{detail} err={err_code} {err_msg or ''}".strip()
        return True, detail
    except Exception as exc:
        logger.exception("alert whatsapp failed")
        return False, str(exc)


def send_alert_email(subject: str, text: str) -> tuple[bool, str]:
    to = (settings.alert_email_to or "").strip()
    host = (settings.smtp_host or "").strip()
    if not to:
        return False, "ALERT_EMAIL_TO vacío"
    if not host:
        return False, "SMTP_HOST vacío"
    user = (settings.smtp_user or "").strip()
    password = settings.smtp_password or ""
    mail_from = (settings.smtp_from or user or to).strip()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = to
    msg.set_content(text)
    try:
        with smtplib.SMTP(host, int(settings.smtp_port or 587), timeout=30) as smtp:
            smtp.starttls()
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
        return True, "ok"
    except Exception as exc:
        logger.exception("alert email failed")
        return False, str(exc)


def notify_owner_human_reply(
    *,
    place_name: str,
    zone: str = "",
    base: str = "",
    phone: str = "",
    body: str = "",
    thread_label: str = "Respuesta humana",
    wait_delivery: bool = False,
) -> dict:
    if not settings.alert_on_human_reply:
        return {"skipped": True, "reason": "ALERT_ON_HUMAN_REPLY=false"}

    text = build_alert_text(
        place_name=place_name,
        zone=zone,
        base=base,
        phone=phone,
        body=body,
        thread_label=thread_label,
    )
    subject = f"SofIA Prioridad: {place_name or 'lead'}"
    result: dict = {"whatsapp": None, "email": None}

    if (settings.alert_whatsapp_to or "").strip():
        if not (settings.alert_whatsapp_template_sid or "").strip():
            logger.warning(
                "ALERT_WHATSAPP_TEMPLATE_SID vacío: freeform suele fallar con 63016 fuera de ventana 24h"
            )
        ok, detail = send_alert_whatsapp(
            text,
            place_name=place_name,
            zone=zone,
            base=base,
            body=body,
            wait_delivery=wait_delivery,
        )
        result["whatsapp"] = {"ok": ok, "detail": detail}
        print(f"[owner_alerts] whatsapp ok={ok} detail={detail}", flush=True)
    if (settings.alert_email_to or "").strip():
        ok, detail = send_alert_email(subject, text)
        result["email"] = {"ok": ok, "detail": detail}

    if result["whatsapp"] is None and result["email"] is None:
        return {
            "skipped": True,
            "reason": "Seteá ALERT_WHATSAPP_TO y/o ALERT_EMAIL_TO (+ SMTP_*)",
        }
    return result
