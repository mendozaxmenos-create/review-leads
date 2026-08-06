"""Campañas de prospección por lote (ej. cabañas Mendoza)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.data.ar_locations import MENDOZA_CABANAS_ZONES, list_mendoza_cabanas_zones
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
from app.config import settings

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])

FIT_PRIORITY = {LeadFit.HIGH: 0, LeadFit.MEDIUM: 1, LeadFit.LOW: 2, LeadFit.NONE: 3}


@router.get("/mendoza-cabanas/zones", response_model=list[CampaignZoneOut])
async def list_zones() -> list[CampaignZoneOut]:
    return [
        CampaignZoneOut(
            id=z.id,
            label=z.label,
            lat=z.lat,
            lng=z.lng,
            radius_km=z.radius_km,
            zoom=z.zoom,
        )
        for z in list_mendoza_cabanas_zones()
    ]


@router.post("/mendoza-cabanas", response_model=MendozaCabanasCampaignResponse)
async def run_mendoza_cabanas(
    body: MendozaCabanasCampaignRequest | None = None,
) -> MendozaCabanasCampaignResponse:
    """Barrido de cabañas en zonas turísticas de Mendoza (etapa 1 Villa Oliva)."""
    req = body or MendozaCabanasCampaignRequest()
    mode = (req.mode or "directory").lower()
    if mode not in ("directory", "leads"):
        raise HTTPException(status_code=400, detail="mode debe ser 'directory' o 'leads'")

    try:
        PlacesService()
        if mode == "leads":
            ReviewClassifier()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    zones = list_mendoza_cabanas_zones()
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
            # Anotar zona en reason si falta contexto
            zone_tag = f"[{zone.label}]"
            if lead.reason and zone_tag not in lead.reason:
                lead.reason = f"{zone_tag} {lead.reason}"
            elif not lead.reason:
                lead.reason = f"{zone_tag} Cabaña / complejo en zona turística Mendoza."

            existing = by_place.get(lead.place_id)
            if not existing:
                by_place[lead.place_id] = lead
                continue
            # Conservar el de mejor fit / más reseñas / con teléfono
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

    # Persistencia agregada en CRM
    center_lat = zones[0].lat if zones else -33.55
    center_lng = zones[0].lng if zones else -69.05
    campaign_history_id = store.save_search_history(
        request={
            "campaign": "mendoza-cabanas",
            "mode": mode,
            "business_type": "cabanas",
            "center": {"lat": center_lat, "lng": center_lng},
            "radius_km": 50,
            "zones": [z.id for z in zones],
            "max_places_per_zone": req.max_places_per_zone,
        },
        response={
            "project_id": "booking-bot",
            "project_name": "Bot de reservas · Mendoza cabañas",
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
        f"Campaña Mendoza cabañas ({mode}): {zones_ok}/{len(zones)} zonas OK, "
        f"{places_scanned} lugares escaneados, {len(leads)} leads únicos "
        f"({with_phone_total} con teléfono). Servicio sugerido: Bot de reservas."
    )

    return MendozaCabanasCampaignResponse(
        campaign="mendoza-cabanas",
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


# Re-export zones constant for scripts
__all__ = ["router", "MENDOZA_CABANAS_ZONES"]
