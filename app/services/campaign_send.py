"""Lógica compartida: enviar campaña WhatsApp Mendoza desde CSV ready o CRM."""

from __future__ import annotations

import asyncio
import csv
from pathlib import Path

from app.config import settings
from app.db.store import get_store
from app.models.schemas import SendCampaignItemResult, SendCampaignResponse
from app.services.twilio_whatsapp import (
    TwilioWhatsAppService,
    extract_zone_from_reason,
    normalize_whatsapp_number,
    resolve_template_region,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_READY_CSV = ROOT / "data" / "exports" / "mendoza-cabanas-etl-clean.csv"
LEGACY_READY_CSV = ROOT / "data" / "exports" / "mendoza-cabanas-ready.csv"


def load_ready_csv(csv_path: Path | None = None, limit: int | None = None) -> list[dict]:
    path = csv_path or (DEFAULT_READY_CSV if DEFAULT_READY_CSV.exists() else LEGACY_READY_CSV)
    if not path.exists():
        raise FileNotFoundError(f"No existe CSV ready: {path}")
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    # Solo ready explícitos o todos si no hay columna
    filtered = []
    for row in rows:
        flag = (row.get("depurar_ready") or "yes").lower()
        if flag in ("no", "false", "0"):
            continue
        if not (row.get("phone") or "").strip():
            continue
        filtered.append(row)
    if limit:
        filtered = filtered[:limit]
    return filtered


def load_crm_new_leads(limit: int | None = None, status: str = "new") -> list[dict]:
    store = get_store()
    store.init()
    # Admin list up to 2000
    rows = store.list_saved_leads_admin(status=status, limit=limit or 2000)
    out: list[dict] = []
    for row in rows:
        lead = row.get("lead") or {}
        phone = lead.get("phone") or ""
        if not phone.strip():
            continue
        # Skip discarded already filtered by status; skip if note says depurado and status wrong
        out.append(
            {
                "place_id": lead.get("place_id") or row.get("place_id"),
                "place_name": lead.get("place_name") or "",
                "phone": phone,
                "reason": lead.get("reason") or "",
                "address": lead.get("address"),
                "saved_lead_id": row.get("id"),
                "status": row.get("status"),
            }
        )
    if limit:
        out = out[:limit]
    return out


async def run_send_campaign(
    *,
    source: str = "csv",
    csv_path: str | None = None,
    dry_run: bool = True,
    limit: int | None = None,
    only_status: str = "new",
    mark_contacted: bool = True,
    update_crm_on_dry_run: bool = False,
) -> SendCampaignResponse:
    twilio = TwilioWhatsAppService()
    live_requested = not dry_run
    if live_requested:
        if not twilio.send_enabled:
            raise ValueError(
                "Envío real bloqueado: seteá TWILIO_SEND_ENABLED=true y dry_run=false"
            )
        ok, msg = twilio.configured_for_live()
        if not ok:
            raise ValueError(msg)

    if source == "crm":
        leads = load_crm_new_leads(limit=limit, status=only_status)
    else:
        path = Path(csv_path) if csv_path else DEFAULT_READY_CSV
        leads = load_ready_csv(path, limit=limit)

    store = get_store()
    store.init()
    place_ids = [str(r.get("place_id") or "") for r in leads if r.get("place_id")]
    crm_meta = store.get_saved_leads_by_places(place_ids)

    items: list[SendCampaignItemResult] = []
    sent_ok = 0
    failed = 0
    crm_updated = 0
    delay = twilio.delay_seconds

    for i, lead in enumerate(leads):
        place_id = str(lead.get("place_id") or "")
        place_name = str(lead.get("place_name") or "")
        phone = str(lead.get("phone") or "")
        zone = resolve_template_region(lead)
        result = twilio.send_template(
            to_phone=phone,
            place_name=place_name,
            zone=zone,
            dry_run=dry_run,
        )

        updated = False
        should_mark = mark_contacted and result.ok and (not result.dry_run or update_crm_on_dry_run)
        if should_mark and place_id:
            info = crm_meta.get(place_id)
            if info and info["status"] == "new":
                store.update_saved_lead(
                    info["saved_lead_id"],
                    status="contacted",
                    notes=(info.get("notes") or "")
                    + ("" if not info.get("notes") else " | ")
                    + ("dry-run Twilio" if result.dry_run else f"Twilio SID {result.sid}"),
                )
                updated = True
                crm_updated += 1

        if result.ok:
            sent_ok += 1
        else:
            failed += 1

        items.append(
            SendCampaignItemResult(
                place_id=place_id,
                place_name=place_name,
                phone=phone,
                to=result.to or normalize_whatsapp_number(phone),
                ok=result.ok,
                dry_run=result.dry_run,
                sid=result.sid,
                status=result.status,
                error=result.error,
                crm_updated=updated,
            )
        )

        if not dry_run and i < len(leads) - 1 and delay > 0:
            await asyncio.sleep(delay)

    mode = "DRY-RUN" if dry_run else "LIVE"
    summary = (
        f"Campaña WhatsApp {mode}: {sent_ok}/{len(leads)} OK, {failed} fallidos, "
        f"{crm_updated} CRM contacted. Delay {delay}s."
    )
    return SendCampaignResponse(
        dry_run=dry_run,
        total=len(leads),
        sent_ok=sent_ok,
        failed=failed,
        crm_updated=crm_updated,
        delay_seconds=delay,
        items=items,
        summary=summary,
    )
