from fastapi import APIRouter, HTTPException, Query

from app.data.ar_locations import AR_PROVINCES, MENDOZA_DEPARTMENTS
from app.models.schemas import GeocodeSuggestion, LocationPresetOut
from app.services.geocode import GeocodeService

router = APIRouter(prefix="/api/geocode", tags=["geocode"])


@router.get("/presets", response_model=list[LocationPresetOut])
async def list_presets() -> list[LocationPresetOut]:
    return [
        LocationPresetOut(
            id=p.id,
            label=p.label,
            lat=p.lat,
            lng=p.lng,
            zoom=p.zoom,
            kind=p.kind,
            group="mendoza" if p.id.startswith("men-") else "argentina",
        )
        for p in AR_PROVINCES + MENDOZA_DEPARTMENTS
    ]


@router.get("/search", response_model=list[GeocodeSuggestion])
async def search_location(
    q: str = Query(..., min_length=2, max_length=120),
    limit: int = Query(default=8, ge=1, le=15),
) -> list[GeocodeSuggestion]:
    try:
        rows = await GeocodeService().search(q, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo geocodificar: {exc}") from exc

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No encontramos esa zona. Probá con ciudad, departamento o dirección en Argentina.",
        )
    return [GeocodeSuggestion.model_validate(row) for row in rows]
