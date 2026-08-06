from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.data.business_types import (
    BUSINESS_TYPE_LABELS,
    all_searchable_types,
    label_for,
    list_search_focuses,
)
from app.data.lead_filters import is_prospectable_place, is_prospectable_rubro
from app.data.services import DISCOVERY_INTRO, get_profile
from app.db.store import get_store
from app.models.schemas import LeadFit, ReviewLead, ReviewSnippet, RubroSummary, SearchRequest, SearchResponse
from app.services.cache import attach_saved_lead_meta, make_search_cache_key
from app.services.classifier import ReviewClassifier
from app.services.places import PlacesService

router = APIRouter(prefix="/api", tags=["search"])

FIT_PRIORITY = {LeadFit.HIGH: 0, LeadFit.MEDIUM: 1, LeadFit.LOW: 2, LeadFit.NONE: 3}


@router.get("/search/focuses")
async def get_search_focuses() -> list[dict]:
    return list_search_focuses()


@router.get("/search/business-types")
async def get_business_types() -> list[dict[str, str]]:
    return [
        {"value": key, "label": label}
        for key, label in BUSINESS_TYPE_LABELS.items()
    ]


@dataclass
class PlaceLeadDraft:
    place_name: str
    place_id: str
    address: str | None
    lat: float | None
    lng: float | None
    phone: str | None
    email: str | None
    website: str | None
    google_maps_url: str | None
    rating: float | None
    business_type: str = "store"
    business_type_label: str = "Negocio"
    best_fit: LeadFit = LeadFit.LOW
    recommended_project_id: str | None = None
    recommended_project_name: str | None = None
    service_votes: Counter = field(default_factory=Counter)
    theme_counts: Counter = field(default_factory=Counter)
    reasons: list[str] = field(default_factory=list)
    pitches: list[str] = field(default_factory=list)
    solution_values: list[str] = field(default_factory=list)
    samples: list[ReviewSnippet] = field(default_factory=list)


def _build_place_lead(draft: PlaceLeadDraft) -> ReviewLead:
    themes = [theme for theme, _ in draft.theme_counts.most_common()]
    theme_line = ", ".join(f"{theme} ({count})" for theme, count in draft.theme_counts.most_common())
    reason = draft.reasons[0] if len(draft.reasons) == 1 else f"Quejas detectadas: {theme_line}."
    pitch = next((p for p in draft.pitches if p), None)
    solution_value = next((s for s in draft.solution_values if s), None)
    review_text = " · ".join(sample.text[:180] for sample in draft.samples[:3])

    if draft.service_votes and not draft.recommended_project_id:
        top_service = draft.service_votes.most_common(1)[0][0]
        profile = get_profile(top_service)
        if profile:
            draft.recommended_project_id = profile.id
            draft.recommended_project_name = profile.name

    return ReviewLead(
        place_name=draft.place_name,
        place_id=draft.place_id,
        address=draft.address,
        lat=draft.lat,
        lng=draft.lng,
        phone=draft.phone,
        email=draft.email,
        website=draft.website,
        google_maps_url=draft.google_maps_url,
        rating=draft.rating,
        lead_fit=draft.best_fit,
        themes=themes,
        theme_counts=dict(draft.theme_counts),
        reviews_count=len(draft.samples),
        review_samples=draft.samples,
        review_text=review_text,
        review_rating=draft.samples[0].rating if draft.samples else None,
        author=draft.samples[0].author if draft.samples else None,
        reason=reason,
        suggested_pitch=pitch,
        solution_value=solution_value,
        business_type=draft.business_type,
        business_type_label=draft.business_type_label,
        recommended_project_id=draft.recommended_project_id,
        recommended_project_name=draft.recommended_project_name,
    )


def _place_passes_rating_filter(place_rating: float | None, max_place_rating: float | None) -> bool:
    if max_place_rating is None:
        return True
    if place_rating is None:
        return True
    return place_rating <= max_place_rating


def _build_rubro_summary(leads: list[ReviewLead]) -> list[RubroSummary]:
    counts: Counter[str] = Counter()
    labels: dict[str, str] = {}
    types: dict[str, str] = {}
    for lead in leads:
        label = lead.business_type_label or label_for(lead.business_type or "store")
        key = lead.business_type or label.lower().replace(" ", "_")
        counts[key] += 1
        labels[key] = label
        types[key] = lead.business_type or key
    return [
        RubroSummary(
            business_type=types[key],
            business_type_label=labels[key],
            leads_count=count,
        )
        for key, count in counts.most_common()
    ]


def _persist_search_result(
    request: SearchRequest,
    response: SearchResponse,
    *,
    from_cache: bool,
) -> SearchResponse:
    store = get_store()
    response_dict = response.model_dump(mode="json")
    history_id = store.save_search_history(
        request=request.model_dump(mode="json"),
        response=response_dict,
        from_cache=from_cache,
    )

    for lead in response.leads:
        saved = store.upsert_saved_lead(
            place_id=lead.place_id,
            lead=lead.model_dump(mode="json"),
            search_history_id=history_id,
        )
        lead.saved_lead_id = saved["saved_lead_id"]
        lead.status = saved["status"]
        lead.notes = saved["notes"]

    response.search_history_id = history_id
    return response


def _apply_service_to_draft(
    draft: PlaceLeadDraft,
    *,
    fit: LeadFit,
    service_id: str | None,
    rubro_label: str,
) -> None:
    if rubro_label:
        draft.business_type_label = rubro_label
    if service_id and fit in (LeadFit.HIGH, LeadFit.MEDIUM, LeadFit.LOW):
        draft.service_votes[service_id] += 1
        profile = get_profile(service_id)
        if profile and (
            draft.recommended_project_id is None
            or FIT_PRIORITY[fit] < FIT_PRIORITY[draft.best_fit]
        ):
            draft.recommended_project_id = profile.id
            draft.recommended_project_name = profile.name


async def _run_search(request: SearchRequest) -> SearchResponse:
    places_service = PlacesService()
    classifier = ReviewClassifier()

    types_filter = [request.business_type] if request.business_type else None
    discovery_items = await places_service.search_discovery(
        lat=request.center.lat,
        lng=request.center.lng,
        radius_km=request.radius_km,
        max_results=request.max_places,
        business_types=types_filter,
        search_focus=request.search_focus,
    )

    place_drafts: dict[str, PlaceLeadDraft] = {}
    reviews_fetched = 0
    reviews_classified = 0
    reviews_skipped = 0

    for item in discovery_items:
        place_summary = item["place"]
        search_business_type = item["business_type"]
        place_id = place_summary.get("id", "")
        if not place_id:
            continue

        try:
            details = await places_service.get_place_details(place_id)
        except Exception:
            continue

        place_name = PlacesService.place_name(details)
        address = details.get("formattedAddress")
        place_rating = details.get("rating")
        lat, lng = PlacesService.extract_location(details)
        inferred_type = PlacesService.infer_business_type(details, search_business_type)
        place_types = details.get("types") or []
        primary_type = details.get("primaryType")

        if not is_prospectable_place(
            place_name,
            primary_type=primary_type,
            types=place_types,
        ):
            skipped_reviews = PlacesService.extract_reviews(details)
            reviews_fetched += len(skipped_reviews)
            reviews_skipped += len(skipped_reviews)
            continue

        type_label = label_for(inferred_type)

        if not _place_passes_rating_filter(place_rating, request.max_place_rating):
            skipped_reviews = PlacesService.extract_reviews(details)
            reviews_fetched += len(skipped_reviews)
            reviews_skipped += len(skipped_reviews)
            continue

        contacts = PlacesService.extract_contacts(details)
        all_reviews = PlacesService.extract_reviews(details)
        reviews_fetched += len(all_reviews)

        reviews_to_classify, skipped = PlacesService.select_reviews_for_analysis(
            all_reviews,
            max_review_rating=request.max_review_rating,
            max_reviews_per_place=request.max_reviews_per_place,
        )
        reviews_skipped += skipped

        for review in reviews_to_classify:
            reviews_classified += 1
            (
                fit,
                theme,
                reason,
                pitch,
                service_id,
                rubro,
                solution_value,
                review_text_es,
                prospectable,
            ) = await classifier.classify_review_discovery(
                place_name=place_name,
                place_address=address,
                business_type_label=type_label,
                review_text=review["text"],
                review_rating=review.get("rating"),
                google_primary_type=primary_type,
            )

            if not prospectable or not is_prospectable_rubro(rubro):
                continue

            if request.project_id and service_id != request.project_id:
                continue

            if fit not in (LeadFit.HIGH, LeadFit.MEDIUM, LeadFit.LOW):
                continue

            if place_id not in place_drafts:
                place_drafts[place_id] = PlaceLeadDraft(
                    place_name=place_name,
                    place_id=place_id,
                    address=address,
                    lat=lat,
                    lng=lng,
                    phone=contacts["phone"],
                    email=contacts["email"],
                    website=contacts["website"],
                    google_maps_url=contacts["google_maps_url"],
                    rating=place_rating,
                    business_type=inferred_type,
                    business_type_label=rubro if is_prospectable_rubro(rubro) else type_label,
                    best_fit=fit,
                )

            draft = place_drafts[place_id]
            if FIT_PRIORITY[fit] < FIT_PRIORITY[draft.best_fit]:
                draft.best_fit = fit
            _apply_service_to_draft(draft, fit=fit, service_id=service_id, rubro_label=rubro)
            draft.theme_counts[theme] += 1
            draft.reasons.append(reason)
            if pitch:
                draft.pitches.append(pitch)
            if solution_value:
                draft.solution_values.append(solution_value)
            draft.samples.append(
                ReviewSnippet(
                    text=review_text_es,
                    rating=review.get("rating"),
                    author=review.get("author"),
                    theme=theme,
                )
            )

    leads = [_build_place_lead(draft) for draft in place_drafts.values()]
    leads.sort(
        key=lambda item: (
            FIT_PRIORITY[item.lead_fit],
            -item.reviews_count,
            item.business_type_label or "",
        )
    )

    summary = await classifier.summarize_leads(
        project_description=DISCOVERY_INTRO,
        leads=leads,
        places_scanned=len(discovery_items),
        reviews_analyzed=reviews_classified,
    )

    return SearchResponse(
        center=request.center,
        radius_km=request.radius_km,
        business_type=request.business_type or "all",
        project_id=None,
        project_name="Detección automática",
        discovery_mode=True,
        mode="leads",
        places_scanned=len(discovery_items),
        reviews_fetched=reviews_fetched,
        reviews_classified=reviews_classified,
        reviews_skipped=reviews_skipped,
        reviews_analyzed=reviews_classified,
        from_cache=False,
        leads=leads,
        summary=summary,
        rubro_summary=_build_rubro_summary(leads),
        category_suggestions=[],
    )


def _default_service_for_type(business_type: str) -> tuple[str | None, str | None]:
    lodging_types = {
        "lodging",
        "hotel",
        "guest_house",
        "cottage",
        "motel",
        "hostel",
        "resort_hotel",
        "bed_and_breakfast",
        "extended_stay_hotel",
        "campground",
    }
    if business_type in lodging_types:
        profile = get_profile("booking-bot")
        if profile:
            return profile.id, profile.name
    return "booking-bot", "Bot de reservas"


async def _run_directory(request: SearchRequest) -> SearchResponse:
    """Lista negocios del rubro/foco sin filtrar por reseñas (modo directorio)."""
    places_service = PlacesService()

    if request.business_type:
        types_filter = [request.business_type]
        focus = None
    else:
        types_filter = None
        focus = request.search_focus or "all"

    discovery_items = await places_service.search_discovery(
        lat=request.center.lat,
        lng=request.center.lng,
        radius_km=request.radius_km,
        max_results=request.max_places,
        business_types=types_filter,
        search_focus=focus,
    )

    leads: list[ReviewLead] = []
    for item in discovery_items:
        place_summary = item["place"]
        search_business_type = item["business_type"]
        place_id = place_summary.get("id", "")
        if not place_id:
            continue

        try:
            details = await places_service.get_place_details(place_id)
        except Exception:
            continue

        place_name = PlacesService.place_name(details)
        address = details.get("formattedAddress")
        place_rating = details.get("rating")
        lat, lng = PlacesService.extract_location(details)
        inferred_type = PlacesService.infer_business_type(details, search_business_type)
        place_types = details.get("types") or []
        primary_type = details.get("primaryType")

        if not is_prospectable_place(
            place_name,
            primary_type=primary_type,
            types=place_types,
        ):
            continue

        if not _place_passes_rating_filter(place_rating, request.max_place_rating):
            continue

        contacts = PlacesService.extract_contacts(details)
        type_label = label_for(inferred_type)
        service_id, service_name = _default_service_for_type(inferred_type)

        leads.append(
            ReviewLead(
                place_name=place_name,
                place_id=place_id,
                address=address,
                lat=lat,
                lng=lng,
                phone=contacts["phone"],
                email=contacts["email"],
                website=contacts["website"],
                google_maps_url=contacts["google_maps_url"],
                rating=place_rating,
                lead_fit=LeadFit.LOW,
                themes=[],
                theme_counts={},
                reviews_count=0,
                review_samples=[],
                review_text="",
                review_rating=None,
                author=None,
                reason="Listado en zona (modo directorio). Ideal para contactar con bot de reservas / WhatsApp.",
                suggested_pitch=None,
                solution_value=None,
                business_type=inferred_type,
                business_type_label=type_label,
                recommended_project_id=service_id,
                recommended_project_name=service_name,
            )
        )

    leads.sort(key=lambda item: (item.business_type_label or "", item.place_name.lower()))
    with_phone = sum(1 for lead in leads if lead.phone)
    rubro_label = label_for(request.business_type) if request.business_type else (
        "Alojamiento turístico" if request.search_focus == "lodging" else "Negocios"
    )
    summary = (
        f"Se listaron {len(leads)} {rubro_label.lower()} en la zona "
        f"({with_phone} con teléfono en Google). "
        f"Marcá contactados desde cada fila o abrí WhatsApp. "
        f"Nota: Google Places no garantiza el 100% de los locales de una ciudad."
    )

    return SearchResponse(
        center=request.center,
        radius_km=request.radius_km,
        business_type=request.business_type or request.search_focus or "all",
        project_id=None,
        project_name="Listado de zona",
        discovery_mode=True,
        mode="directory",
        places_scanned=len(discovery_items),
        reviews_fetched=0,
        reviews_classified=0,
        reviews_skipped=0,
        reviews_analyzed=0,
        from_cache=False,
        leads=leads,
        summary=summary,
        rubro_summary=_build_rubro_summary(leads),
        category_suggestions=[],
    )


@router.post("/search", response_model=SearchResponse)
async def search_leads(request: SearchRequest) -> SearchResponse:
    if request.project_id and not get_profile(request.project_id) and not request.project_description:
        raise HTTPException(
            status_code=400,
            detail=f"project_id '{request.project_id}' no existe. Ver GET /api/projects",
        )

    mode = (request.mode or "leads").lower()
    if mode not in ("leads", "directory"):
        raise HTTPException(status_code=400, detail="mode debe ser 'leads' o 'directory'")

    try:
        PlacesService()
        if mode == "leads":
            ReviewClassifier()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    store = get_store()
    cache_key = make_search_cache_key(request)

    if request.use_cache:
        cached = store.get_search_cache(cache_key)
        if cached:
            attach_saved_lead_meta(
                cached,
                store.get_saved_leads_by_places(
                    [lead["place_id"] for lead in cached.get("leads", [])]
                ),
            )
            response = SearchResponse.model_validate({**cached, "from_cache": True})
            return _persist_search_result(request, response, from_cache=True)

    try:
        response = await _run_directory(request) if mode == "directory" else await _run_search(request)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Error al consultar Google Places: {exc}",
        ) from exc

    if request.use_cache:
        store.set_search_cache(
            cache_key,
            response.model_dump(mode="json"),
            settings.cache_ttl_hours,
        )

    return _persist_search_result(request, response, from_cache=False)
