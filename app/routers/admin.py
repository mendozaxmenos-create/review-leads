from fastapi import APIRouter

from app.db.store import get_store
from app.models.lead_status import LEAD_STATUS_PIPELINE, status_label, status_to_code
from app.models.schemas import AdminLeadOut, AdminStatsOut, LeadStatusInfo

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _to_admin_lead(row: dict) -> AdminLeadOut:
    status = row["status"]
    return AdminLeadOut(
        id=row["id"],
        place_id=row["place_id"],
        status=status,
        status_code=status_to_code(status),
        status_label=status_label(status),
        notes=row["notes"],
        updated_at=row["updated_at"],
        lead=row["lead"],
        project_id=row.get("project_id"),
        project_name=row.get("project_name"),
        business_type=row.get("business_type"),
        search_at=row.get("search_at"),
    )


@router.get("/statuses", response_model=list[LeadStatusInfo])
async def list_statuses() -> list[LeadStatusInfo]:
    return [
        LeadStatusInfo(code=step.code, value=step.value, label=step.label)
        for step in LEAD_STATUS_PIPELINE
    ]


@router.get("/stats", response_model=AdminStatsOut)
async def admin_stats() -> AdminStatsOut:
    by_status = get_store().count_leads_by_status()
    by_status_code = {status_to_code(status): count for status, count in by_status.items()}
    return AdminStatsOut(
        total=sum(by_status.values()),
        by_status=by_status,
        by_status_code=by_status_code,
    )


@router.get("/projects")
async def admin_projects() -> list[dict[str, str | None]]:
    return get_store().list_admin_project_filters()


@router.get("/leads", response_model=list[AdminLeadOut])
async def list_admin_leads(
    status: str | None = None,
    project_id: str | None = None,
    lead_fit: str | None = None,
    limit: int = 500,
) -> list[AdminLeadOut]:
    rows = get_store().list_saved_leads_admin(
        status=status,
        project_id=project_id,
        lead_fit=lead_fit,
        limit=min(limit, 1000),
    )
    return [_to_admin_lead(row) for row in rows]
