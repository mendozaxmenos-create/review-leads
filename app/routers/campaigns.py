"""Campañas de prospección por lote (ej. cabañas Mendoza / Córdoba)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import settings
from app.data.ar_locations import (
    CampaignZone,
    MENDOZA_CABANAS_ZONES,
    list_cordoba_cabanas_zones,
    list_mendoza_cabanas_zones,
)
from app.data.services import get_profile
from app.db.store import get_store
from app.models.schemas import (
    CampaignZoneOut,
    CampaignZoneResult,
    GeoPoint,
    LeadFit,
    MendozaCabanasCampaignRequest,
    MendozaCabanasCampaignResponse,
    ReviewLead,
    SearchRequest,
    SearchResponse,
)
from app.routers import search as search_router
from app.services.cache import make_search_cache_key
from app.services.classifier import ReviewClassifier
from app.services.places import PlacesService

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])

FIT_PRIORITY = {LeadFit.HIGH: 0, LeadFit.MEDIUM: 1, LeadFit.LOW: 2, LeadFit.NONE: 3}


def _zones_out(zones: list[CampaignZone]) -> list[CampaignZoneOut]:
    return [
        CampaignZoneOut(
            id=z.id,
            label=z.label,
            lat=z.lat,
            lng=z.lng,
            radius_km=z.radius_km,
            zoom=z.zoom,
        )
        for z in zones
    ]


@router.get("/mendoza-cabanas/zones", response_model=list[CampaignZoneOut])
async def list_zones() -> list[CampaignZoneOut]:
    return _zones_out(list_mendoza_cabanas_zones())


@router.get("/cordoba-cabanas/zones", response_model=list[CampaignZoneOut])
async def list_cordoba_zones() -> list[CampaignZoneOut]:
    return _zones_out(list_cordoba_cabanas_zones())


async def run_cabanas_zones(
    *,
    zones: list[CampaignZone],
    req: MendozaCabanasCampaignRequest,
    campaign: str,
    region_label: str,
    default_center: tuple[float, float],
) -> MendozaCabanasCampaignResponse:
    """Barrido compartido de cabañas por lista de zonas (Mendoza, Córdoba, …)."""
    mode = (req.mode or "directory").lower()
    if mode not in ("directory", "leads"):
        raise HTTPException(status_code=400, detail="mode debe ser 'directory' o 'leads'")

    try:
        PlacesService()
        if mode == "leads":
            ReviewClassifier()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if req.zone_ids:
        wanted = set(req.zone_ids)
        zones = [z for z in zones if z.id in wanted]
        if not zones:
            raise HTTPException(status_code=400, detail="Ninguna zone_id válida")

    booking = get_profile("booking-bot")
    store = get_store()
    by_place: dict[str, ReviewLead] = {}
    zone_results: list[CampaignZoneResult] = []
    places_scanned = 0
    zones_ok = 0

    for i, zone in enumerate(zones, start=1):
        print(f"[{i}/{len(zones)}] {zone.label}…", flush=True)
        search_req = SearchRequest(
            center=GeoPoint(lat=zone.lat, lng=zone.lng),
            radius_km=zone.radius_km,
            search_focus="cabanas",
            mode=mode,
            max_places=req.max_places_per_zone,
            use_cache=req.use_cache,
            max_review_rating=req.max_review_rating if mode == "leads" else None,
            max_reviews_per_place=req.max_reviews_per_place,
        )

        zone_error: str | None = None
        zone_leads: list[ReviewLead] = []
        zone_places = 0
        history_id: int | None = None

        try:
            cache_key = make_search_cache_key(search_req)
            cached = store.get_search_cache(cache_key) if req.use_cache else None
            if cached:
                from app.services.cache import attach_saved_lead_meta

                attach_saved_lead_meta(
                    cached,
                    store.get_saved_leads_by_places(
                        [lead["place_id"] for lead in cached.get("leads", [])]
                    ),
                )
                response = SearchResponse.model_validate(
                    {**cached, "from_cache": True}
                )
                response = search_router._persist_search_result(
                    search_req, response, from_cache=True
                )
            else:
                if mode == "directory":
                    response = await search_router._run_directory(search_req)
                else:
                    response = await search_router._run_search(search_req)
                if req.use_cache:
                    store.set_search_cache(
                        cache_key,
                        response.model_dump(mode="json"),
                        settings.cache_ttl_hours,
                    )
                response = search_router._persist_search_result(
                    search_req, response, from_cache=False
                )

            zone_leads = response.leads
            zone_places = response.places_scanned
            history_id = response.search_history_id
            zones_ok += 1
            print(
                f"  -> {len(zone_leads)} leads ({sum(1 for lead in zone_leads if lead.phone)} tel)",
                flush=True,
            )
        except Exception as exc:
            zone_error = str(exc)
            print(f"  -> ERROR: {zone_error}", flush=True)

        places_scanned += zone_places
        with_phone = sum(1 for lead in zone_leads if lead.phone)

        for lead in zone_leads:
            if booking:
                lead.recommended_project_id = booking.id
                lead.recommended_project_name = booking.name
            zone_tag = f"[{zone.label}]"
            if lead.reason and zone_tag not in lead.reason:
                lead.reason = f"{zone_tag} {lead.reason}"
            elif not lead.reason:
                lead.reason = f"{zone_tag} Cabaña / complejo en zona turística {region_label}."

            existing = by_place.get(lead.place_id)
            if not existing:
                by_place[lead.place_id] = lead
                continue
            if FIT_PRIORITY.get(lead.lead_fit, 9) < FIT_PRIORITY.get(existing.lead_fit, 9):
                by_place[lead.place_id] = lead
            elif (lead.phone and not existing.phone) or (
                (lead.reviews_count or 0) > (existing.reviews_count or 0)
            ):
                by_place[lead.place_id] = lead

        zone_results.append(
            CampaignZoneResult(
                zone_id=zone.id,
                zone_label=zone.label,
                places_scanned=zone_places,
                leads_count=len(zone_leads),
                with_phone=with_phone,
                error=zone_error,
                search_history_id=history_id,
            )
        )

    leads = list(by_place.values())
    leads.sort(
        key=lambda item: (
            0 if item.phone else 1,
            FIT_PRIORITY.get(item.lead_fit, 9),
            -(item.reviews_count or 0),
            item.place_name.lower(),
        )
    )

    center_lat = zones[0].lat if zones else default_center[0]
    center_lng = zones[0].lng if zones else default_center[1]
    campaign_history_id = store.save_search_history(
        request={
            "campaign": campaign,
            "mode": mode,
            "business_type": "cabanas",
            "center": {"lat": center_lat, "lng": center_lng},
            "radius_km": 50,
            "zones": [z.id for z in zones],
            "max_places_per_zone": req.max_places_per_zone,
        },
        response={
            "project_id": "booking-bot",
            "project_name": f"Bot de reservas · {region_label} cabañas",
            "places_scanned": places_scanned,
            "leads": [lead.model_dump(mode="json") for lead in leads],
            "leads_unique": len(leads),
            "zones": [z.model_dump() for z in zone_results],
        },
        from_cache=False,
    )
    for lead in leads:
        saved = store.upsert_saved_lead(
            place_id=lead.place_id,
            lead=lead.model_dump(mode="json"),
            search_history_id=campaign_history_id,
        )
        lead.saved_lead_id = saved["saved_lead_id"]
        lead.status = saved["status"]
        lead.notes = saved["notes"]

    with_phone_total = sum(1 for lead in leads if lead.phone)
    summary = (
        f"Campaña {region_label} cabañas ({mode}): {zones_ok}/{len(zones)} zonas OK, "
        f"{places_scanned} lugares escaneados, {len(leads)} leads únicos "
        f"({with_phone_total} con teléfono). Servicio sugerido: Bot de reservas."
    )

    return MendozaCabanasCampaignResponse(
        campaign=campaign,
        mode=mode,
        zones_total=len(zones),
        zones_ok=zones_ok,
        places_scanned=places_scanned,
        leads_unique=len(leads),
        with_phone=with_phone_total,
        zones=zone_results,
        leads=leads,
        summary=summary,
        search_history_id=campaign_history_id,
    )


@router.post("/mendoza-cabanas", response_model=MendozaCabanasCampaignResponse)
async def run_mendoza_cabanas(
    body: MendozaCabanasCampaignRequest | None = None,
) -> MendozaCabanasCampaignResponse:
    """Barrido de cabañas en zonas turísticas de Mendoza."""
    req = body or MendozaCabanasCampaignRequest()
    return await run_cabanas_zones(
        zones=list_mendoza_cabanas_zones(),
        req=req,
        campaign="mendoza-cabanas",
        region_label="Mendoza",
        default_center=(-33.55, -69.05),
    )


@router.post("/cordoba-cabanas", response_model=MendozaCabanasCampaignResponse)
async def run_cordoba_cabanas(
    body: MendozaCabanasCampaignRequest | None = None,
) -> MendozaCabanasCampaignResponse:
    """Barrido de cabañas en Punilla + Calamuchita (base Córdoba)."""
    req = body or MendozaCabanasCampaignRequest()
    return await run_cabanas_zones(
        zones=list_cordoba_cabanas_zones(),
        req=req,
        campaign="cordoba-cabanas",
        region_label="Córdoba",
        default_center=(-31.42, -64.50),
    )


# Re-export zones constant for scripts
__all__ = ["router", "MENDOZA_CABANAS_ZONES", "run_cabanas_zones", "run_cordoba_cabanas"]


@router.post("/mendoza-cabanas/sync")
async def sync_mendoza_etl(body: dict | None = None) -> dict:
    """Importa CSV ETL limpio al CRM (tag mendoza-cabanas-etl).

    Body opcional JSON:
      { "csv_path": "data/exports/cordoba-cabanas-etl-clean.csv", "base_name": "Córdoba" }
    """
    from app.services.mendoza_campaign import sync_etl_clean_to_crm

    payload = body or {}
    csv_path = Path(payload["csv_path"]) if payload.get("csv_path") else None
    if csv_path and not csv_path.is_absolute():
        csv_path = Path(__file__).resolve().parents[2] / csv_path
    base_name = payload.get("base_name")
    try:
        return sync_etl_clean_to_crm(csv_path=csv_path, base_name=base_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/mendoza-cabanas/upload")
async def upload_mendoza_csv(
    file: UploadFile = File(...),
    base_name: str = Form(default="Mendoza"),
) -> dict:
    """Sube un CSV de campaña y lo sincroniza al CRM (con nombre de base/región).

    Guarda siempre `campaign-{base}.csv`. Solo pisa `mendoza-cabanas-etl-clean.csv`
    cuando la base es Mendoza (no sobrescribe el clean activo al subir Córdoba).
    """
    from app.services.mendoza_campaign import CAMPAIGN_TAG, sync_etl_clean_to_crm

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Subí un archivo .csv")
    export_dir = Path(__file__).resolve().parents[2] / "data" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    base = (base_name or "Mendoza").strip() or "Mendoza"
    safe_base = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in base)[:40]
    dest = export_dir / f"campaign-{safe_base or 'base'}.csv"
    content = await file.read()
    dest.write_bytes(content)
    sync_path = dest
    if base.casefold() in {"mendoza"}:
        active = export_dir / "mendoza-cabanas-etl-clean.csv"
        active.write_bytes(content)
        sync_path = active
    result = sync_etl_clean_to_crm(csv_path=sync_path, base_name=base)
    result["campaign_tag"] = CAMPAIGN_TAG
    result["saved_as"] = str(dest)
    result["sync_path"] = str(sync_path)
    result["overwrote_mendoza_clean"] = base.casefold() in {"mendoza"}
    return result


@router.get("/mendoza-cabanas/dashboard")
def mendoza_wa_dashboard() -> dict:
    """Sync def → threadpool: no bloquea el event loop ni el resto del refresh."""
    from app.services.mendoza_campaign import campaign_dashboard_stats

    return campaign_dashboard_stats()


@router.get("/mendoza-cabanas/twilio-billing")
def mendoza_twilio_billing() -> dict:
    """Saldo y uso cobrado (carga aparte para no colgar el dashboard)."""
    from app.services.mendoza_campaign import twilio_billing_snapshot

    return twilio_billing_snapshot()


@router.get("/mendoza-cabanas/bases/{base_name}/sent-zones")
async def mendoza_base_sent_zones(base_name: str) -> dict:
    """Zonas ya contactadas de una base concreta."""
    from app.services.mendoza_campaign import CAMPAIGN_ID, CAMPAIGN_TAG

    store = get_store()
    store.init()
    base = (base_name or "").strip() or "Mendoza"
    zones = store.list_sent_zones_for_base(
        campaign_id=CAMPAIGN_ID,
        campaign_tag=CAMPAIGN_TAG,
        base=base,
        live_only=True,
    )
    return {"base": base, "zones": zones, "count": len(zones)}


@router.get("/mendoza-cabanas/kpi/{kpi}")
async def mendoza_wa_kpi_leads(
    kpi: str, limit: int = 500, zone: str | None = None
) -> dict:
    """Contactos asociados a un KPI del dashboard (clic en la card)."""
    from app.services.mendoza_campaign import list_kpi_leads

    try:
        return list_kpi_leads(kpi, limit=min(limit, 2000), zone=zone)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/mendoza-cabanas/sends")
def mendoza_wa_sends(limit: int = 100, live_only: bool = False) -> list[dict]:
    from app.services.mendoza_campaign import CAMPAIGN_ID

    store = get_store()
    store.init()
    return store.list_campaign_sends(CAMPAIGN_ID, limit=min(limit, 500), only_live=live_only)


@router.get("/mendoza-cabanas/leads")
async def mendoza_wa_leads(limit: int = 500) -> list[dict]:
    from app.services.mendoza_campaign import CAMPAIGN_TAG

    store = get_store()
    store.init()
    rows = store.list_leads_by_campaign_tag(CAMPAIGN_TAG, limit=min(limit, 2000))
    return [
        {
            "id": r["id"],
            "place_id": r["place_id"],
            "status": r["status"],
            "notes": r["notes"],
            "updated_at": r["updated_at"],
            "lead": r["lead"],
        }
        for r in rows
    ]


@router.post("/mendoza-cabanas/send-wa")
async def send_mendoza_wa(body: dict | None = None) -> dict:
    """Cola de envío WhatsApp (dry_run=true por defecto). Bloquea live si remitente es Sandbox US."""
    from app.services.mendoza_campaign import run_mendoza_wa_campaign

    payload = body or {}
    try:
        result = await run_mendoza_wa_campaign(
            dry_run=bool(payload.get("dry_run", True)),
            limit=payload.get("limit"),
            skip_already_sent=bool(payload.get("skip_already_sent", True)),
            mark_contacted=bool(payload.get("mark_contacted", True)),
            update_crm_on_dry_run=bool(payload.get("update_crm_on_dry_run", False)),
            base_name=(payload.get("base_name") or payload.get("base") or "").strip() or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result.model_dump()


@router.get("/mendoza-cabanas/responded")
def list_responded(limit: int = 100) -> list[dict]:
    return _list_campaign_status_leads("responded", limit)


@router.get("/mendoza-cabanas/follow-up")
def list_follow_up(limit: int = 100) -> list[dict]:
    """Leads que ya contestaste vos (seguimiento fuera de Twilio)."""
    return _list_campaign_status_leads("follow_up", limit)


@router.get("/mendoza-cabanas/priority")
def list_priority(limit: int = 100) -> list[dict]:
    """Priority operativos: humano / empty en responded+follow_up (no closed/lost)."""
    from app.services.campaign_ops import is_priority_thread

    responded = _list_campaign_status_leads("responded", limit)
    follow = _list_campaign_status_leads("follow_up", limit)
    seen: set[str] = set()
    out: list[dict] = []
    for item in [*responded, *follow]:
        pid = item.get("place_id")
        if not pid or pid in seen:
            continue
        if not is_priority_thread(item.get("reply_thread_kind")):
            continue
        if item.get("ops_stage") in {"closed", "lost"}:
            continue
        seen.add(pid)
        out.append(item)
    by_pri: dict[int, list[dict]] = {}
    for item in out:
        by_pri.setdefault(int(item.get("reply_priority", 9)), []).append(item)
    ordered: list[dict] = []
    for pri in sorted(by_pri):
        bucket = by_pri[pri]
        bucket.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        ordered.extend(bucket)
    return ordered


@router.post("/mendoza-cabanas/ops-stage")
async def set_ops_stage(body: dict) -> dict:
    """Marca etapa de cierre ops: pending|contacted|demo|closed|lost."""
    from app.services.campaign_ops import (
        OPS_STAGE_LABELS,
        normalize_ops_stage,
        pipeline_status_for_ops,
    )

    place_id = (body or {}).get("place_id")
    stage = normalize_ops_stage((body or {}).get("ops_stage") or (body or {}).get("stage"))
    if not place_id:
        raise HTTPException(status_code=400, detail="place_id requerido")
    if not stage:
        raise HTTPException(
            status_code=400,
            detail="ops_stage debe ser pending|contacted|demo|closed|lost",
        )
    store = get_store()
    store.init()
    meta = store.get_saved_leads_by_places([place_id]).get(place_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    note = (meta.get("notes") or "").strip()
    label = OPS_STAGE_LABELS[stage]
    stage_note = f"Ops: {label}"
    new_notes = note if note.endswith(stage_note) else (note + (" | " if note else "") + stage_note)
    store.update_saved_lead(
        meta["saved_lead_id"],
        status=pipeline_status_for_ops(stage),
        notes=new_notes,
        lead_fields={"ops_stage": stage},
    )
    return {
        "ok": True,
        "place_id": place_id,
        "ops_stage": stage,
        "ops_stage_label": label,
        "status": pipeline_status_for_ops(stage),
    }


def _list_campaign_status_leads(status: str, limit: int) -> list[dict]:
    from app.routers.demo import public_demo_share_url
    from app.services.campaign_ops import (
        OPS_STAGE_LABELS,
        demo_url_for_place,
        resolve_ops_stage,
    )
    from app.services.mendoza_campaign import CAMPAIGN_ID, CAMPAIGN_TAG
    from app.services.reply_classify import classify_inbound_body, classify_inbound_thread

    store = get_store()
    store.init()
    rows = store.list_campaign_leads_by_status(CAMPAIGN_TAG, status, limit=min(limit, 500))
    demo_base = public_demo_share_url() or "https://review-leads.onrender.com/demo"
    out = []
    for r in rows:
        lead = r["lead"]
        msgs = store.list_campaign_messages(
            CAMPAIGN_ID, place_id=r["place_id"], limit=40
        )
        inbound = [m for m in reversed(msgs) if m.get("direction") == "inbound"]
        thread = classify_inbound_thread([m.get("body") for m in inbound])
        last_in = inbound[-1] if inbound else None
        phone = lead.get("phone") or ""
        digits = "".join(ch for ch in phone if ch.isdigit())
        ops = resolve_ops_stage(r["status"], lead)
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
        out.append(
            {
                "id": r["id"],
                "place_id": r["place_id"],
                "place_name": lead.get("place_name"),
                "zone": lead.get("zone"),
                "base": lead.get("base") or "Mendoza",
                "phone": phone,
                "status": r["status"],
                "ops_stage": ops,
                "ops_stage_label": OPS_STAGE_LABELS[ops],
                "notes": r["notes"],
                "updated_at": r["updated_at"],
                "last_reply": (last_in or {}).get("body"),
                "inbound_replies": inbound_replies,
                "reply_thread_kind": thread["thread_kind"],
                "reply_thread_label": thread["thread_label"],
                "reply_last_kind": thread["last_kind"],
                "reply_last_kind_label": thread["last_kind_label"],
                "reply_needs_you": thread["needs_you"],
                "reply_waiting_human": thread["waiting_human_possible"],
                "reply_inbound_count": thread["inbound_count"],
                "reply_priority": thread["priority"],
                "wa_me": f"https://wa.me/{digits}" if digits else None,
                "demo_url": demo_url_for_place(lead.get("place_name"), demo_base),
                "mailto": f"mailto:{lead['email']}" if lead.get("email") else None,
            }
        )
    # Humanos / retomaron primero; solo-auto después (aún pueden retomar)
    by_pri: dict[int, list[dict]] = {}
    for item in out:
        by_pri.setdefault(int(item.get("reply_priority", 9)), []).append(item)
    ordered: list[dict] = []
    for pri in sorted(by_pri):
        bucket = by_pri[pri]
        bucket.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        ordered.extend(bucket)
    return ordered


@router.get("/mendoza-cabanas/messages")
async def list_messages(place_id: str | None = None, limit: int = 100) -> list[dict]:
    from app.services.mendoza_campaign import CAMPAIGN_ID

    store = get_store()
    store.init()
    return store.list_campaign_messages(CAMPAIGN_ID, place_id=place_id, limit=min(limit, 500))


@router.post("/mendoza-cabanas/handoff")
async def mark_handoff(body: dict) -> dict:
    """Marca que ya contestaste: pasa a En seguimiento (fuera de Twilio)."""
    place_id = (body or {}).get("place_id")
    channel = (body or {}).get("channel") or "whatsapp_personal"
    if not place_id:
        raise HTTPException(status_code=400, detail="place_id requerido")
    store = get_store()
    store.init()
    meta = store.get_saved_leads_by_places([place_id]).get(place_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    note = (meta.get("notes") or "").strip()
    handoff = f"Ya contesté vía {channel}"
    store.update_saved_lead(
        meta["saved_lead_id"],
        status="follow_up",
        notes=(note + (" | " if note else "") + handoff),
        lead_fields={"ops_stage": "contacted"},
    )
    return {"ok": True, "place_id": place_id, "channel": channel, "status": "follow_up", "ops_stage": "contacted"}


@router.post("/mendoza-cabanas/discard")
async def discard_lead(body: dict) -> dict:
    """STOP / no interesado: sale de Contestaron y En seguimiento."""
    place_id = (body or {}).get("place_id")
    reason = ((body or {}).get("reason") or "STOP / no interesado").strip()
    if not place_id:
        raise HTTPException(status_code=400, detail="place_id requerido")
    store = get_store()
    store.init()
    meta = store.get_saved_leads_by_places([place_id]).get(place_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    note = (meta.get("notes") or "").strip()
    discard_note = f"Descartado: {reason}"
    store.update_saved_lead(
        meta["saved_lead_id"],
        status="discarded",
        notes=(note + (" | " if note else "") + discard_note),
        lead_fields={"ops_stage": "lost"},
    )
    return {"ok": True, "place_id": place_id, "status": "discarded", "ops_stage": "lost"}


@router.post("/mendoza-cabanas/alerts/test")
async def test_owner_alert() -> dict:
    """Envía un aviso de prueba a ALERT_WHATSAPP_TO / ALERT_EMAIL_TO."""
    from app.services.owner_alerts import notify_owner_human_reply

    result = notify_owner_human_reply(
        place_name="Prueba SofIA",
        zone="test",
        base="test",
        phone="+54900000000",
        body="Este es un aviso de prueba del KPI Prioridad (humano).",
        thread_label="Prueba de alerta",
        wait_delivery=True,
    )
    return {"ok": True, "result": result}
