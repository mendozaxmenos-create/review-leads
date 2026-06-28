from fastapi import APIRouter, HTTPException

from app.data.services import get_profile, list_profiles
from app.db.store import get_store
from app.models.schemas import CustomProjectCreate, CustomProjectUpdate, ServiceProfileOut

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _to_out(profile, *, is_custom: bool = False) -> ServiceProfileOut:
    return ServiceProfileOut(
        id=profile.id,
        name=profile.name,
        description=profile.description,
        lead_criteria=profile.lead_criteria,
        suggested_business_types=profile.suggested_business_types,
        is_custom=is_custom,
    )


@router.get("", response_model=list[ServiceProfileOut])
async def get_projects() -> list[ServiceProfileOut]:
    builtin = [_to_out(profile) for profile in list_profiles()]
    custom = [_to_out(profile, is_custom=True) for profile in get_store().list_custom_projects()]
    return builtin + custom


@router.get("/{project_id}", response_model=ServiceProfileOut)
async def get_project(project_id: str) -> ServiceProfileOut:
    profile = get_profile(project_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Proyecto '{project_id}' no encontrado")
    is_custom = project_id.startswith("custom-")
    return _to_out(profile, is_custom=is_custom)


@router.post("/custom", response_model=ServiceProfileOut, status_code=201)
async def create_custom_project(body: CustomProjectCreate) -> ServiceProfileOut:
    profile = get_store().create_custom_project(
        name=body.name,
        description=body.description,
        lead_criteria=body.lead_criteria,
        suggested_business_types=body.suggested_business_types,
    )
    return _to_out(profile, is_custom=True)


@router.put("/custom/{project_id}", response_model=ServiceProfileOut)
async def update_custom_project(project_id: str, body: CustomProjectUpdate) -> ServiceProfileOut:
    if not project_id.startswith("custom-"):
        raise HTTPException(status_code=400, detail="Solo se pueden editar servicios custom")
    profile = get_store().update_custom_project(
        project_id,
        name=body.name,
        description=body.description,
        lead_criteria=body.lead_criteria,
        suggested_business_types=body.suggested_business_types,
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Servicio custom no encontrado")
    return _to_out(profile, is_custom=True)


@router.delete("/custom/{project_id}", status_code=204)
async def delete_custom_project(project_id: str) -> None:
    if not project_id.startswith("custom-"):
        raise HTTPException(status_code=400, detail="Solo se pueden eliminar servicios custom")
    if not get_store().delete_custom_project(project_id):
        raise HTTPException(status_code=404, detail="Servicio custom no encontrado")
