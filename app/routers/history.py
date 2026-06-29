from fastapi import APIRouter, HTTPException

from app.db.store import get_store
from app.models.lead_status import status_label, status_to_code
from app.models.schemas import SavedLeadOut, SavedLeadUpdate, SearchHistoryItem, SearchResponse

router = APIRouter(prefix="/api/history", tags=["history"])


def _to_saved_lead_out(row: dict) -> SavedLeadOut:
    status = row["status"]
    return SavedLeadOut(
        id=row["id"],
        place_id=row["place_id"],
        status=status,
        status_code=status_to_code(status),
        status_label=status_label(status),
        notes=row["notes"],
        updated_at=row["updated_at"],
        lead=row["lead"],
    )


@router.get("/searches", response_model=list[SearchHistoryItem])
async def list_searches(limit: int = 30) -> list[SearchHistoryItem]:
    rows = get_store().list_search_history(limit=min(limit, 100))
    return [
        SearchHistoryItem(
            id=row["id"],
            created_at=row["created_at"],
            project_id=row.get("project_id"),
            project_name=row.get("project_name"),
            business_type=row["business_type"],
            center_lat=row["center_lat"],
            center_lng=row["center_lng"],
            radius_km=row["radius_km"],
            places_scanned=row["places_scanned"],
            leads_count=row["leads_count"],
            from_cache=bool(row["from_cache"]),
        )
        for row in rows
    ]


@router.get("/searches/{history_id}", response_model=SearchResponse)
async def get_search(history_id: int) -> SearchResponse:
    row = get_store().get_search_history(history_id)
    if not row:
        raise HTTPException(status_code=404, detail="Búsqueda no encontrada")
    response = row["response"]
    response["search_history_id"] = history_id
    return SearchResponse.model_validate(response)


@router.get("/leads", response_model=list[SavedLeadOut])
async def list_saved_leads(status: str | None = None, limit: int = 100) -> list[SavedLeadOut]:
    rows = get_store().list_saved_leads(status=status, limit=min(limit, 200))
    return [_to_saved_lead_out(row) for row in rows]


@router.patch("/leads/{saved_lead_id}", response_model=SavedLeadOut)
async def update_saved_lead(saved_lead_id: int, body: SavedLeadUpdate) -> SavedLeadOut:
    row = get_store().update_saved_lead(
        saved_lead_id,
        status=body.status.value if body.status else None,
        notes=body.notes,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    return _to_saved_lead_out(row)
