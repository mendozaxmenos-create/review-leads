from fastapi import APIRouter, HTTPException

from app.data.services import get_profile, list_profiles
from app.models.schemas import ServiceProfileOut

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ServiceProfileOut])
async def get_projects() -> list[ServiceProfileOut]:
    return [
        ServiceProfileOut(
            id=profile.id,
            name=profile.name,
            description=profile.description,
            lead_criteria=profile.lead_criteria,
            suggested_business_types=profile.suggested_business_types,
        )
        for profile in list_profiles()
    ]


@router.get("/{project_id}", response_model=ServiceProfileOut)
async def get_project(project_id: str) -> ServiceProfileOut:
    profile = get_profile(project_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Proyecto '{project_id}' no encontrado")
    return ServiceProfileOut(
        id=profile.id,
        name=profile.name,
        description=profile.description,
        lead_criteria=profile.lead_criteria,
        suggested_business_types=profile.suggested_business_types,
    )
