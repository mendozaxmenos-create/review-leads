from fastapi import APIRouter, HTTPException

from app.data.services import get_profile
from app.models.schemas import LeadFit, ReviewLead, SearchRequest, SearchResponse
from app.services.category_suggester import CategorySuggester
from app.services.classifier import ReviewClassifier
from app.services.places import PlacesService

router = APIRouter(prefix="/api", tags=["search"])


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


@router.post("/search", response_model=SearchResponse)
async def search_leads(request: SearchRequest) -> SearchResponse:
    project_description, lead_criteria, project_name = _resolve_project(request)

    try:
        places_service = PlacesService()
        classifier = ReviewClassifier()
        suggester = CategorySuggester()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    try:
        places = await places_service.search_nearby(
            lat=request.center.lat,
            lng=request.center.lng,
            radius_km=request.radius_km,
            business_type=request.business_type,
            max_results=request.max_places,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Error al consultar Google Places: {exc}",
        ) from exc

    leads: list[ReviewLead] = []
    reviews_analyzed = 0

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
        contacts = PlacesService.extract_contacts(details)

        for review in PlacesService.extract_reviews(details):
            reviews_analyzed += 1
            fit, reason, pitch = await classifier.classify_review(
                project_description=project_description,
                lead_criteria=lead_criteria,
                place_name=place_name,
                place_address=address,
                review_text=review["text"],
                review_rating=review.get("rating"),
            )

            if fit in (LeadFit.HIGH, LeadFit.MEDIUM, LeadFit.LOW):
                leads.append(
                    ReviewLead(
                        place_name=place_name,
                        place_id=place_id,
                        address=address,
                        phone=contacts["phone"],
                        website=contacts["website"],
                        google_maps_url=contacts["google_maps_url"],
                        rating=place_rating,
                        review_text=review["text"],
                        review_rating=review.get("rating"),
                        author=review.get("author"),
                        lead_fit=fit,
                        reason=reason,
                        suggested_pitch=pitch,
                    )
                )

    leads.sort(
        key=lambda item: {"high": 0, "medium": 1, "low": 2, "none": 3}[item.lead_fit.value]
    )

    relevant_leads = sum(1 for lead in leads if lead.lead_fit in (LeadFit.HIGH, LeadFit.MEDIUM))

    summary = await classifier.summarize_leads(
        project_description=project_description,
        leads=leads,
        places_scanned=len(places),
        reviews_analyzed=reviews_analyzed,
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
        reviews_analyzed=reviews_analyzed,
        leads=leads,
        summary=summary,
        category_suggestions=category_suggestions,
    )
