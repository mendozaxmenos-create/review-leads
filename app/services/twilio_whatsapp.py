"""Envío de WhatsApp vía Twilio (plantillas Content API)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

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
    """Usa el tag [Zona] del reason (ej. [Cosquín] …). Vacío si no hay tag."""
    text = reason or ""
    m = re.match(r"\[([^\]]+)\]", text.strip())
    if m:
        return m.group(1).strip()
    return ""


def resolve_template_region(lead: dict | None, *, fallback: str = "tu zona") -> str:
    """{{2}} de la plantilla: zona del lead, si no la base (Córdoba/Mendoza), si no fallback genérico."""
    row = lead or {}
    zone = (row.get("zone") or "").strip() or extract_zone_from_reason(row.get("reason"))
    if zone:
        return zone[:60]
    base = (row.get("base") or "").strip()
    if base:
        return base[:60]
    return (fallback or "tu zona")[:60]


def _twilio_auth() -> tuple[str, str] | None:
    sid = settings.twilio_account_sid.strip()
    token = settings.twilio_auth_token.strip()
    if not sid or not token:
        return None
    return sid, token


def fetch_twilio_balance(*, timeout: float = 5.0) -> dict[str, Any]:
    """Saldo de cuenta Twilio (GET Balance). Soft-fail si faltan creds o la API falla."""
    auth = _twilio_auth()
    if not auth:
        return {
            "ok": False,
            "balance": None,
            "currency": None,
            "error": "Faltan TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN",
        }
    sid, token = auth
    try:
        import httpx
    except ImportError:
        return {
            "ok": False,
            "balance": None,
            "currency": None,
            "error": "httpx no instalado",
        }
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Balance.json"
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url, auth=(sid, token))
        if resp.status_code != 200:
            detail = (resp.text or "")[:160]
            return {
                "ok": False,
                "balance": None,
                "currency": None,
                "error": f"HTTP {resp.status_code}: {detail}",
            }
        data = resp.json()
        raw = data.get("balance")
        try:
            amount = float(raw) if raw is not None else None
        except (TypeError, ValueError):
            amount = None
        return {
            "ok": True,
            "balance": amount,
            "currency": (data.get("currency") or "USD").strip().upper() or "USD",
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "balance": None,
            "currency": None,
            "error": str(exc)[:200],
        }


def _parse_usage_price(payload: dict[str, Any]) -> tuple[float | None, str]:
    rows = payload.get("usage_records") or []
    if not rows:
        return 0.0, "USD"
    row = rows[0]
    raw = row.get("price")
    try:
        amount = float(raw) if raw is not None else 0.0
    except (TypeError, ValueError):
        amount = None
    unit = (row.get("price_unit") or "usd").strip().upper() or "USD"
    return amount, unit


def fetch_twilio_usage(*, timeout: float = 6.0) -> dict[str, Any]:
    """Uso cobrado (Usage Records totalprice): mes actual + all-time. Soft-fail."""
    auth = _twilio_auth()
    if not auth:
        return {
            "ok": False,
            "this_month": None,
            "all_time": None,
            "currency": None,
            "whatsapp_marketing_count": None,
            "error": "Faltan TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN",
        }
    sid, token = auth
    try:
        import httpx
    except ImportError:
        return {
            "ok": False,
            "this_month": None,
            "all_time": None,
            "currency": None,
            "whatsapp_marketing_count": None,
            "error": "httpx no instalado",
        }
    base = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Usage/Records"
    try:
        from concurrent.futures import ThreadPoolExecutor

        def _get(path: str, category: str):
            with httpx.Client(timeout=timeout) as client:
                return client.get(
                    f"{base}/{path}",
                    auth=(sid, token),
                    params={"Category": category},
                )

        with ThreadPoolExecutor(max_workers=3) as pool:
            fut_month = pool.submit(_get, "ThisMonth.json", "totalprice")
            fut_all = pool.submit(_get, "AllTime.json", "totalprice")
            fut_wa = pool.submit(
                _get, "ThisMonth.json", "channels-whatsapp-template-marketing"
            )
            month = fut_month.result()
            all_time = fut_all.result()
            wa = fut_wa.result()
        if month.status_code != 200:
            detail = (month.text or "")[:160]
            return {
                "ok": False,
                "this_month": None,
                "all_time": None,
                "currency": None,
                "whatsapp_marketing_count": None,
                "error": f"HTTP {month.status_code}: {detail}",
            }
        this_month, currency = _parse_usage_price(month.json())
        all_amt: float | None = None
        if all_time.status_code == 200:
            all_amt, cur2 = _parse_usage_price(all_time.json())
            currency = currency or cur2
        wa_count: int | None = None
        if wa.status_code == 200:
            rows = (wa.json() or {}).get("usage_records") or []
            if rows:
                try:
                    wa_count = int(float(rows[0].get("count") or 0))
                except (TypeError, ValueError):
                    wa_count = None
        return {
            "ok": True,
            "this_month": this_month,
            "all_time": all_amt,
            "currency": currency or "USD",
            "whatsapp_marketing_count": wa_count,
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "this_month": None,
            "all_time": None,
            "currency": None,
            "whatsapp_marketing_count": None,
            "error": str(exc)[:200],
        }


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
                        "2": (zone or "tu zona")[:60],
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
