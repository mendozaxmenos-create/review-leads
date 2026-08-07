"""Campaña Mendoza · cabañas: sync CSV→CRM, envío con log, stats dashboard."""

from __future__ import annotations

import asyncio
import csv
from pathlib import Path

from app.db.store import get_store
from app.models.schemas import (
    SendCampaignItemResult,
    SendCampaignResponse,
)
from app.services.campaign_send import DEFAULT_READY_CSV, LEGACY_READY_CSV, load_ready_csv
from app.services.twilio_whatsapp import (
    TwilioWhatsAppService,
    extract_zone_from_reason,
    normalize_whatsapp_number,
)

CAMPAIGN_ID = "mendoza-cabanas-wa"
CAMPAIGN_TAG = "mendoza-cabanas-etl"


def csv_path_default() -> Path:
    if DEFAULT_READY_CSV.exists():
        return DEFAULT_READY_CSV
    return LEGACY_READY_CSV


def sync_etl_clean_to_crm(*, csv_path: Path | None = None) -> dict:
    """Importa leads del CSV limpio al CRM (upsert). No pisa status contacted/responded/closed."""
    path = csv_path or csv_path_default()
    rows = load_ready_csv(path)
    store = get_store()
    store.init()

    # History row for tagging
    history_id = store.save_search_history(
        request={
            "campaign": CAMPAIGN_TAG,
            "source_csv": str(path),
            "business_type": "cabanas",
            "center": {"lat": -33.55, "lng": -69.05},
            "radius_km": 50,
        },
        response={
            "project_id": "booking-bot",
            "project_name": "Bot de reservas · Mendoza cabañas",
            "places_scanned": len(rows),
            "leads": [],
        },
        from_cache=False,
    )

    inserted = 0
    updated = 0
    skipped_terminal = 0
    existing = store.get_saved_leads_by_places([r.get("place_id", "") for r in rows if r.get("place_id")])

    for row in rows:
        place_id = (row.get("place_id") or "").strip()
        if not place_id:
            continue
        prev = existing.get(place_id)
        if prev and prev["status"] in ("contacted", "responded", "closed"):
            # Refresh JSON lightly via upsert but status preserved by store upsert
            skipped_terminal += 1

        zone = (row.get("zone") or "").strip() or extract_zone_from_reason(row.get("reason"))
        lead = {
            "place_name": row.get("place_name"),
            "place_id": place_id,
            "address": row.get("address"),
            "phone": row.get("phone") or row.get("phone_e164"),
            "website": row.get("website"),
            "google_maps_url": row.get("google_maps_url"),
            "rating": float(row["rating"]) if (row.get("rating") or "").strip() else None,
            "lead_fit": row.get("lead_fit") or "low",
            "themes": [],
            "theme_counts": {},
            "reviews_count": 0,
            "review_text": "",
            "reason": row.get("reason") or f"[{zone}] Campaña Mendoza cabañas",
            "suggested_pitch": None,
            "solution_value": None,
            "business_type": "cottage",
            "business_type_label": row.get("business_type_label") or "Cabañas",
            "recommended_project_id": "booking-bot",
            "recommended_project_name": "Bot de reservas",
            "campaign": CAMPAIGN_TAG,
            "zone": zone,
        }
        before = prev is not None
        store.upsert_saved_lead(place_id=place_id, lead=lead, search_history_id=history_id)
        if before:
            updated += 1
        else:
            inserted += 1

    return {
        "csv": str(path),
        "rows": len(rows),
        "inserted": inserted,
        "updated": updated,
        "skipped_terminal_refresh": skipped_terminal,
        "history_id": history_id,
    }


def campaign_dashboard_stats() -> dict:
    store = get_store()
    store.init()
    send_stats = store.campaign_send_stats(CAMPAIGN_ID)
    sent_ids = store.campaign_sent_place_ids(CAMPAIGN_ID, live_only=True)
    by_status = store.count_leads_by_campaign_status(CAMPAIGN_TAG)
    crm_tagged = sum(by_status.values())

    try:
        csv_rows = load_ready_csv(csv_path_default())
        csv_ids = {r.get("place_id") for r in csv_rows if r.get("place_id")}
    except FileNotFoundError:
        csv_rows = []
        csv_ids = set()

    universe = len(csv_ids) if csv_ids else crm_tagged
    pending = max(0, len(csv_ids - sent_ids)) if csv_ids else by_status.get("new", 0)
    responded = by_status.get("responded", 0)
    contacted = by_status.get("contacted", 0)

    return {
        "campaign": CAMPAIGN_ID,
        "universe": universe,
        "csv_rows": len(csv_rows),
        "crm_tagged": crm_tagged,
        "by_status": by_status,
        "pending_to_send": pending,
        "sent_live_unique": len(sent_ids),
        "contacted": contacted,
        "responded": responded,
        "send_log": send_stats,
        "blockers": _blockers(),
        "handoff_hint": (
            "Cuando contestan: el webhook marca responded. "
            "Abrí la charla en TU WhatsApp (wa.me) para no seguir pagando Twilio."
        ),
        "webhook_inbound": "/api/twilio/whatsapp/inbound",
    }


def _blockers() -> list[str]:
    twilio = TwilioWhatsAppService()
    blockers: list[str] = []
    if not twilio.account_sid or not twilio.auth_token:
        blockers.append("Faltan TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN")
    if not twilio.from_number or "14155238886" in twilio.from_number:
        blockers.append("Remitente sigue en Sandbox US — falta número WhatsApp +54")
    if not twilio.template_sid:
        blockers.append("Falta TWILIO_TEMPLATE_SID (plantilla marketing aprobada)")
    if not twilio.send_enabled:
        blockers.append("TWILIO_SEND_ENABLED=false (dry-run only)")
    return blockers


async def run_mendoza_wa_campaign(
    *,
    dry_run: bool = True,
    limit: int | None = None,
    skip_already_sent: bool = True,
    mark_contacted: bool = True,
    update_crm_on_dry_run: bool = False,
) -> SendCampaignResponse:
    """Envía plantilla a leads del CSV limpio; loguea y marca CRM."""
    twilio = TwilioWhatsAppService()
    if not dry_run:
        if not twilio.send_enabled:
            raise ValueError("TWILIO_SEND_ENABLED=false")
        ok, msg = twilio.configured_for_live()
        if not ok:
            raise ValueError(msg)
        if "14155238886" in (twilio.from_number or ""):
            raise ValueError(
                "No se puede hacer blast live desde Sandbox US. Configurá TWILIO_WHATSAPP_FROM=+54…"
            )

    leads = load_ready_csv(csv_path_default(), limit=None)
    store = get_store()
    store.init()

    already = store.campaign_sent_place_ids(CAMPAIGN_ID, live_only=True) if skip_already_sent else set()
    queue = []
    for row in leads:
        pid = row.get("place_id") or ""
        if skip_already_sent and not dry_run and pid in already:
            continue
        # Also skip CRM already contacted/responded/closed on live
        queue.append(row)

    crm_meta = store.get_saved_leads_by_places([r.get("place_id", "") for r in queue if r.get("place_id")])
    if not dry_run:
        filtered = []
        for row in queue:
            info = crm_meta.get(row.get("place_id") or "")
            if info and info["status"] in ("contacted", "responded", "closed", "discarded"):
                continue
            filtered.append(row)
        queue = filtered

    if limit:
        queue = queue[:limit]

    items: list[SendCampaignItemResult] = []
    sent_ok = 0
    failed = 0
    crm_updated = 0
    delay = twilio.delay_seconds

    for i, lead in enumerate(queue):
        place_id = str(lead.get("place_id") or "")
        place_name = str(lead.get("place_name") or "")
        phone = str(lead.get("phone") or lead.get("phone_e164") or "")
        zone = (lead.get("zone") or "").strip() or extract_zone_from_reason(lead.get("reason"))

        result = twilio.send_template(
            to_phone=phone,
            place_name=place_name,
            zone=zone or "Mendoza",
            dry_run=dry_run,
        )

        store.log_campaign_send(
            campaign=CAMPAIGN_ID,
            place_id=place_id,
            place_name=place_name,
            phone=phone,
            zone=zone,
            dry_run=result.dry_run,
            ok=result.ok,
            twilio_sid=result.sid,
            twilio_status=result.status,
            error=result.error,
        )
        if result.ok and not result.dry_run:
            store.log_campaign_message(
                campaign=CAMPAIGN_ID,
                place_id=place_id,
                phone=phone,
                direction="outbound",
                body=f"[plantilla] {place_name} / {zone or 'Mendoza'} / $19.000",
                twilio_sid=result.sid,
            )

        updated = False
        should_mark = mark_contacted and result.ok and (not result.dry_run or update_crm_on_dry_run)
        if should_mark and place_id:
            info = crm_meta.get(place_id)
            if info and info["status"] == "new":
                note = "dry-run Twilio" if result.dry_run else f"Twilio SID {result.sid}"
                prev_notes = info.get("notes") or ""
                store.update_saved_lead(
                    info["saved_lead_id"],
                    status="contacted",
                    notes=(prev_notes + (" | " if prev_notes else "") + note),
                )
                updated = True
                crm_updated += 1
            elif not info:
                # Ensure CRM row exists then mark
                store.upsert_saved_lead(
                    place_id=place_id,
                    lead={
                        "place_name": place_name,
                        "place_id": place_id,
                        "phone": phone,
                        "address": lead.get("address"),
                        "reason": lead.get("reason") or f"[{zone}] Campaña Mendoza",
                        "review_text": "",
                        "lead_fit": "low",
                        "recommended_project_id": "booking-bot",
                        "recommended_project_name": "Bot de reservas",
                        "campaign": CAMPAIGN_TAG,
                        "zone": zone,
                        "business_type_label": lead.get("business_type_label"),
                    },
                    search_history_id=None,
                )
                meta2 = store.get_saved_leads_by_places([place_id]).get(place_id)
                if meta2:
                    store.update_saved_lead(
                        meta2["saved_lead_id"],
                        status="contacted",
                        notes=f"Twilio SID {result.sid}" if result.sid else "campaña WhatsApp",
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

        if not dry_run and i < len(queue) - 1 and delay > 0:
            await asyncio.sleep(delay)

    mode = "DRY-RUN" if dry_run else "LIVE"
    summary = (
        f"Campaña {CAMPAIGN_ID} {mode}: {sent_ok}/{len(queue)} OK, {failed} fallidos, "
        f"{crm_updated} CRM contacted."
    )
    return SendCampaignResponse(
        dry_run=dry_run,
        total=len(queue),
        sent_ok=sent_ok,
        failed=failed,
        crm_updated=crm_updated,
        delay_seconds=delay,
        items=items,
        summary=summary,
    )
