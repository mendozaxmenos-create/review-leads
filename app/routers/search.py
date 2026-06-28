from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.data.services import get_profile
from app.db.store import get_store
from app.models.schemas import LeadFit, ReviewLead, ReviewSnippet, SearchRequest, SearchResponse
from app.services.cache import attach_saved_lead_meta, make_search_cache_key
from app.services.category_suggester import CategorySuggester
from app.services.classifier import ReviewClassifier
from app.services.places import PlacesService

router = APIRouter(prefix="/api", tags=["search"])

FIT_PRIORITY = {LeadFit.HIGH: 0, LeadFit.MEDIUM: 1, LeadFit.LOW: 2, LeadFit.NONE: 3}


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
    best_fit: LeadFit = LeadFit.LOW
    theme_counts: Counter = field(default_factory=Counter)
    reasons: list[str] = field(default_factory=list)
    pitches: list[str] = field(default_factory=list)
    samples: list[ReviewSnippet] = field(default_factory=list)


def _resolve_project(request: SearchRequest) -> tuple[str, str | None, str | None]:
    if request.project_id:
        profile = get_profile(request.project_id)
        if not profile:
            raise HTTPException(
                status_code=400,
                detail=f"project_id '{request.project_id}' no existe. Ver GET /api/projects",
            )
        criteria = profile.lead_criteria
        if request.lead_criteria:
            criteria = f"{criteria}\n\nCriterios adicionales: {request.lead_criteria}"
        return profile.description, criteria, profile.name

    assert request.project_description
    return request.project_description, request.lead_criteria, None


def _build_place_lead(draft: PlaceLeadDraft) -> ReviewLead:
    themes = [theme for theme, _ in draft.theme_counts.most_common()]
    theme_line = ", ".join(f"{theme} ({count})" for theme, count in draft.theme_counts.most_common())
    reason = draft.reasons[0] if len(draft.reasons) == 1 else f"Quejas detectadas: {theme_line}."
    pitch = next((p for p in draft.pitches if p), None)
    review_text = " · ".join(sample.text[:180] for sample in draft.samples[:3])

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
    )


def _place_passes_rating_filter(place_rating: float | None, max_place_rating: float | None) -> bool:
    if max_place_rating is None:
        return True
    if place_rating is None:
        return True
    return place_rating <= max_place_rating


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


async def _run_search(request: SearchRequest, project_name: str | None) -> SearchResponse:
    project_description, lead_criteria, resolved_name = _resolve_project(request)
    project_name = project_name or resolved_name

    places_service = PlacesService()
    classifier = ReviewClassifier()
    suggester = CategorySuggester()

    places = await places_service.search_nearby(
        lat=request.center.lat,
        lng=request.center.lng,
        radius_km=request.radius_km,
        business_type=request.business_type,
        max_results=request.max_places,
    )

    place_drafts: dict[str, PlaceLeadDraft] = {}
    reviews_fetched = 0
    reviews_classified = 0
    reviews_skipped = 0

    for place_summary in places:
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
            fit, theme, reason, pitch = await classifier.classify_review(
                project_description=project_description,
                lead_criteria=lead_criteria,
                place_name=place_name,
                place_address=address,
                review_text=review["text"],
                review_rating=review.get("rating"),
            )

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
                    best_fit=fit,
                )

            draft = place_drafts[place_id]
            if FIT_PRIORITY[fit] < FIT_PRIORITY[draft.best_fit]:
                draft.best_fit = fit
            draft.theme_counts[theme] += 1
            draft.reasons.append(reason)
            if pitch:
                draft.pitches.append(pitch)
            draft.samples.append(
                ReviewSnippet(
                    text=review["text"],
                    rating=review.get("rating"),
                    author=review.get("author"),
                    theme=theme,
                )
            )

    leads = [_build_place_lead(draft) for draft in place_drafts.values()]
    leads.sort(key=lambda item: (FIT_PRIORITY[item.lead_fit], -item.reviews_count))

    relevant_leads = sum(1 for lead in leads if lead.lead_fit in (LeadFit.HIGH, LeadFit.MEDIUM))

    summary = await classifier.summarize_leads(
        project_description=project_description,
        leads=leads,
        places_scanned=len(places),
        reviews_analyzed=reviews_classified,
    )

    category_suggestions = await suggester.suggest(
        center=request.center,
        radius_km=request.radius_km,
        current_business_type=request.business_type,
        project_id=request.project_id,
        project_description=project_description,
        places_found=len(places),
        relevant_leads=relevant_leads,
    )

    return SearchResponse(
        center=request.center,
        radius_km=request.radius_km,
        business_type=request.business_type,
        project_id=request.project_id,
        project_name=project_name,
        places_scanned=len(places),
        reviews_fetched=reviews_fetched,
        reviews_classified=reviews_classified,
        reviews_skipped=reviews_skipped,
        reviews_analyzed=reviews_classified,
        from_cache=False,
        leads=leads,
        summary=summary,
        category_suggestions=category_suggestions,
    )


@router.post("/search", response_model=SearchResponse)
async def search_leads(request: SearchRequest) -> SearchResponse:
    if request.project_id and not get_profile(request.project_id) and not request.project_description:
        raise HTTPException(
            status_code=400,
            detail=f"project_id '{request.project_id}' no existe. Ver GET /api/projects",
        )

    try:
        PlacesService()
        ReviewClassifier()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    store = get_store()
    cache_key = make_search_cache_key(request)

    if request.use_cache:
        cached = store.get_search_cache(cache_key)
        if cached:
            attach_saved_lead_meta(cached, store.get_saved_leads_by_places(
                [lead["place_id"] for lead in cached.get("leads", [])]
            ))
            response = SearchResponse.model_validate({**cached, "from_cache": True})
            return _persist_search_result(request, response, from_cache=True)

    try:
        response = await _run_search(request, project_name=None)
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
