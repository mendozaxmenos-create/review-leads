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


def sync_etl_clean_to_crm(
    *,
    csv_path: Path | None = None,
    base_name: str | None = None,
) -> dict:
    """Importa leads del CSV limpio al CRM (upsert). No pisa status contacted/responded/closed."""
    path = csv_path or csv_path_default()
    rows = load_ready_csv(path)
    store = get_store()
    store.init()
    base = (base_name or "Mendoza").strip() or "Mendoza"

    # History row for tagging
    history_id = store.save_search_history(
        request={
            "campaign": CAMPAIGN_TAG,
            "base": base,
            "source_csv": str(path),
            "business_type": "cabanas",
            "center": {"lat": -33.55, "lng": -69.05},
            "radius_km": 50,
        },
        response={
            "project_id": "booking-bot",
            "project_name": f"Bot de reservas · {base}",
            "places_scanned": len(rows),
            "leads": [],
        },
        from_cache=False,
    )

    inserted = 0
    updated = 0
    skipped_terminal = 0
    skipped_already_elsewhere = 0
    existing = store.get_saved_leads_by_places([r.get("place_id", "") for r in rows if r.get("place_id")])
    already_sent_places = store.all_live_sent_place_ids()
    already_sent_phones = store.all_live_sent_phone_digits()

    for row in rows:
        place_id = (row.get("place_id") or "").strip()
        if not place_id:
            continue
        prev = existing.get(place_id)
        if prev and prev["status"] in ("contacted", "responded", "follow_up", "closed"):
            skipped_terminal += 1

        zone = (row.get("zone") or "").strip() or extract_zone_from_reason(row.get("reason"))
        phone = row.get("phone") or row.get("phone_e164") or ""
        phone_digits = "".join(ch for ch in str(phone) if ch.isdigit())
        phone_key = phone_digits[-10:] if len(phone_digits) >= 10 else phone_digits
        already_messaged = place_id in already_sent_places or (
            bool(phone_key) and phone_key in already_sent_phones
        )
        if already_messaged and not prev:
            skipped_already_elsewhere += 1

        lead = {
            "place_name": row.get("place_name"),
            "place_id": place_id,
            "address": row.get("address"),
            "phone": phone,
            "website": row.get("website"),
            "google_maps_url": row.get("google_maps_url"),
            "rating": float(row["rating"]) if (row.get("rating") or "").strip() else None,
            "lead_fit": row.get("lead_fit") or "low",
            "themes": [],
            "theme_counts": {},
            "reviews_count": 0,
            "review_text": "",
            "reason": row.get("reason") or f"[{zone}] Campaña {base}",
            "suggested_pitch": None,
            "solution_value": None,
            "business_type": "cottage",
            "business_type_label": row.get("business_type_label") or "Cabañas",
            "recommended_project_id": "booking-bot",
            "recommended_project_name": "Bot de reservas",
            "campaign": CAMPAIGN_TAG,
            "zone": zone,
            "base": base,
            "already_messaged": already_messaged,
        }
        before = prev is not None
        store.upsert_saved_lead(place_id=place_id, lead=lead, search_history_id=history_id)
        if before:
            updated += 1
        else:
            inserted += 1

    return {
        "csv": str(path),
        "base": base,
        "rows": len(rows),
        "inserted": inserted,
        "updated": updated,
        "skipped_terminal_refresh": skipped_terminal,
        "already_messaged_in_other_send": skipped_already_elsewhere,
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
    follow_up = by_status.get("follow_up", 0)

    from app.services.reply_classify import classify_inbound_thread

    responded_human = 0
    responded_auto = 0
    for r in store.list_campaign_leads_by_status(CAMPAIGN_TAG, "responded", limit=500):
        msgs = store.list_campaign_messages(CAMPAIGN_ID, place_id=r["place_id"], limit=40)
        inbound = [m for m in reversed(msgs) if m.get("direction") == "inbound"]
        thread = classify_inbound_thread([m.get("body") for m in inbound])
        if thread["thread_kind"] == "auto_only":
            responded_auto += 1
        else:
            responded_human += 1

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
        "responded_human": responded_human,
        "responded_auto": responded_auto,
        "follow_up": follow_up,
        "send_log": send_stats,
        "blockers": _blockers(),
        "handoff_hint": (
            "El bot del alojamiento respondió solo. No está cerrado: si un humano escribe después, "
            "el lead salta a la sección «Prioridad» de arriba. "
            "Cuando vos ya les respondiste, tocá «Ya contesté» → En seguimiento."
        ),
        "webhook_inbound": "/api/twilio/whatsapp/inbound",
        "bases": store.list_campaign_bases(CAMPAIGN_TAG),
        "sent_zones": store.list_sent_zones(CAMPAIGN_ID, live_only=True),
    }


_KPI_LABELS = {
    "base": "En base",
    "pending": "Pendientes de envío",
    "sent": "Enviados (Twilio live)",
    "contacted": "Sin reply (contactados)",
    "responded_human": "Por contestar (humano)",
    "responded_auto": "Solo auto-reply",
    "follow_up": "En seguimiento",
    "discarded": "Descartados",
}


def list_kpi_leads(kpi: str, *, limit: int = 500, zone: str | None = None) -> dict:
    """Leads asociados a un KPI del dashboard de campaña."""
    from app.services.reply_classify import classify_inbound_thread

    key = (kpi or "base").strip().lower()
    if key not in _KPI_LABELS:
        raise ValueError(f"KPI desconocido: {kpi}. Válidos: {', '.join(_KPI_LABELS)}")

    store = get_store()
    store.init()
    sent_ids = store.campaign_sent_place_ids(CAMPAIGN_ID, live_only=True)
    zone_filter = (zone or "").strip() or None
    if zone_filter and key == "sent":
        sent_ids = set(store.sent_place_ids_for_zone(CAMPAIGN_ID, zone_filter, live_only=True))
    crm_by_place = {
        r["place_id"]: r
        for r in store.list_leads_by_campaign_tag(CAMPAIGN_TAG, limit=2000)
        if r.get("place_id")
    }

    try:
        csv_rows = load_ready_csv(csv_path_default())
    except FileNotFoundError:
        csv_rows = []
    csv_by_place = {r["place_id"]: r for r in csv_rows if r.get("place_id")}

    def _row_out(place_id: str, *, status: str | None = None, lead: dict | None = None, notes: str | None = None) -> dict:
        crm = crm_by_place.get(place_id)
        csv = csv_by_place.get(place_id) or {}
        lead_data = lead or (crm["lead"] if crm else {}) or {}
        if not lead_data.get("place_name") and csv:
            lead_data = {
                "place_name": csv.get("place_name") or csv.get("name"),
                "zone": csv.get("zone") or extract_zone_from_reason(csv.get("reason") or ""),
                "phone": csv.get("phone"),
                "email": csv.get("email"),
                "address": csv.get("address"),
            }
        phone = lead_data.get("phone") or ""
        digits = "".join(ch for ch in phone if ch.isdigit())
        st = status if status is not None else (crm["status"] if crm else "new")
        return {
            "id": crm["id"] if crm else None,
            "place_id": place_id,
            "status": st,
            "notes": notes if notes is not None else (crm.get("notes") if crm else None),
            "updated_at": crm.get("updated_at") if crm else None,
            "place_name": lead_data.get("place_name"),
            "zone": lead_data.get("zone"),
            "phone": phone,
            "wa_me": f"https://wa.me/{digits}" if digits else None,
            "lead": lead_data,
        }

    def _attach_thread(item: dict) -> dict:
        from app.services.reply_classify import classify_inbound_body

        pid = item.get("place_id")
        if not pid:
            return item
        msgs = store.list_campaign_messages(CAMPAIGN_ID, place_id=pid, limit=40)
        inbound = [m for m in reversed(msgs) if m.get("direction") == "inbound"]
        thread = classify_inbound_thread([m.get("body") for m in inbound])
        inbound_replies = []
        for m in inbound:
            body = (m.get("body") or "").strip()
            kind = classify_inbound_body(body)
            inbound_replies.append(
                {
                    "body": body,
                    "kind": kind,
                    "kind_label": {
                        "auto_reply": "Auto-reply (bot)",
                        "human": "Humano",
                        "stop": "Opt-out / STOP",
                        "empty": "Sin texto",
                    }.get(kind, kind),
                    "created_at": m.get("created_at"),
                }
            )
        item["inbound_replies"] = inbound_replies
        item["reply_thread_kind"] = thread["thread_kind"]
        item["reply_thread_label"] = thread["thread_label"]
        item["reply_last_kind"] = thread["last_kind"]
        item["reply_last_kind_label"] = thread["last_kind_label"]
        item["reply_inbound_count"] = thread["inbound_count"]
        item["last_reply"] = (inbound[-1].get("body") if inbound else None)
        # Tipo amigable según KPI / estado
        st = item.get("status") or ""
        if key == "pending":
            item["reply_thread_kind"] = "pending"
            item["reply_thread_label"] = "Pendiente de envío"
        elif key == "sent" and not inbound:
            item["reply_thread_kind"] = "sent"
            item["reply_thread_label"] = "Enviado · sin reply"
        elif key == "contacted" and not inbound:
            item["reply_thread_kind"] = "contacted"
            item["reply_thread_label"] = "Contactado · sin reply"
        elif key == "base" and not inbound:
            labels = {
                "new": "En base · sin enviar",
                "contacted": "Contactado · sin reply",
                "responded": "Respondió",
                "follow_up": "En seguimiento",
                "discarded": "Descartado",
            }
            item["reply_thread_kind"] = st or "base"
            item["reply_thread_label"] = labels.get(st, st or "En base")
        return item

    def _responded_split(want_auto: bool) -> list[dict]:
        out: list[dict] = []
        for r in store.list_campaign_leads_by_status(CAMPAIGN_TAG, "responded", limit=500):
            item = _row_out(
                r["place_id"],
                status=r["status"],
                lead=r["lead"],
                notes=r.get("notes"),
            )
            item = _attach_thread(item)
            is_auto = item.get("reply_thread_kind") == "auto_only"
            if want_auto != is_auto:
                continue
            out.append(item)
        return out[:limit]

    leads: list[dict] = []
    if key == "base":
        place_ids = list(csv_by_place.keys()) if csv_by_place else list(crm_by_place.keys())
        leads = [_attach_thread(_row_out(pid)) for pid in place_ids[:limit]]
    elif key == "pending":
        global_sent = store.all_live_sent_place_ids()
        if csv_by_place:
            pending_ids = [pid for pid in csv_by_place if pid not in global_sent]
        else:
            pending_ids = [
                pid
                for pid, r in crm_by_place.items()
                if r.get("status") == "new" and pid not in global_sent
            ]
        leads = [_attach_thread(_row_out(pid)) for pid in pending_ids[:limit]]
    elif key == "sent":
        leads = [_attach_thread(_row_out(pid)) for pid in list(sent_ids)[:limit]]
    elif key == "contacted":
        for r in store.list_campaign_leads_by_status(CAMPAIGN_TAG, "contacted", limit=limit):
            leads.append(
                _attach_thread(
                    _row_out(r["place_id"], status=r["status"], lead=r["lead"], notes=r.get("notes"))
                )
            )
    elif key == "follow_up":
        for r in store.list_campaign_leads_by_status(CAMPAIGN_TAG, "follow_up", limit=limit):
            leads.append(
                _attach_thread(
                    _row_out(r["place_id"], status=r["status"], lead=r["lead"], notes=r.get("notes"))
                )
            )
    elif key == "discarded":
        for r in store.list_campaign_leads_by_status(CAMPAIGN_TAG, "discarded", limit=limit):
            leads.append(
                _attach_thread(
                    _row_out(r["place_id"], status=r["status"], lead=r["lead"], notes=r.get("notes"))
                )
            )
    elif key == "responded_human":
        leads = _responded_split(want_auto=False)
    elif key == "responded_auto":
        leads = _responded_split(want_auto=True)

    return {
        "kpi": key,
        "label": _KPI_LABELS[key] + (f" · {zone_filter}" if zone_filter and key == "sent" else ""),
        "count": len(leads),
        "zone": zone_filter,
        "leads": leads,
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

    already_places = store.all_live_sent_place_ids() if skip_already_sent else set()
    already_phones = store.all_live_sent_phone_digits() if skip_already_sent else set()
    # También los de esta campaña (por si all_* falla en edge cases)
    already_places |= store.campaign_sent_place_ids(CAMPAIGN_ID, live_only=True) if skip_already_sent else set()
    queue = []
    skipped_dup = 0
    for row in leads:
        pid = row.get("place_id") or ""
        phone = str(row.get("phone") or row.get("phone_e164") or "")
        digits = "".join(ch for ch in phone if ch.isdigit())
        phone_key = digits[-10:] if len(digits) >= 10 else digits
        if skip_already_sent and not dry_run:
            if pid in already_places or (phone_key and phone_key in already_phones):
                skipped_dup += 1
                continue
        queue.append(row)

    crm_meta = store.get_saved_leads_by_places([r.get("place_id", "") for r in queue if r.get("place_id")])
    if not dry_run:
        filtered = []
        for row in queue:
            info = crm_meta.get(row.get("place_id") or "")
            if info and info["status"] in ("contacted", "responded", "follow_up", "closed", "discarded"):
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
        f"{crm_updated} CRM contacted"
        + (f", {skipped_dup} omitidos (ya enviados en alguna base)" if skipped_dup else "")
        + "."
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
