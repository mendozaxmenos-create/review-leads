from enum import Enum

from pydantic import BaseModel, Field, model_validator


class LeadFit(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class GeoPoint(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class ServiceProfileOut(BaseModel):
    id: str
    name: str
    description: str
    lead_criteria: str
    suggested_business_types: list[str]


class SearchRequest(BaseModel):
    """Busca negocios cercanos y clasifica sus reseñas como leads potenciales."""

    center: GeoPoint
    radius_km: float = Field(..., gt=0, le=50, description="Radio de búsqueda en kilómetros")
    business_type: str = Field(
        default="restaurant",
        description="Tipo de negocio (Google Places type), ej: restaurant, store, gym",
    )
    max_places: int = Field(default=20, ge=1, le=60)
    project_id: str | None = Field(
        default=None,
        description="ID de un servicio predefinido (ai, booking-bot, crm, it-solutions, apps, cursor-dev)",
    )
    project_description: str | None = Field(
        default=None,
        min_length=10,
        description="Descripción custom del servicio (si no usás project_id)",
    )
    lead_criteria: str | None = Field(
        default=None,
        description="Criterios adicionales opcionales para considerar un lead",
    )

    @model_validator(mode="after")
    def require_project_source(self) -> "SearchRequest":
        if not self.project_id and not self.project_description:
            raise ValueError("Indicá project_id o project_description")
        return self


class ReviewLead(BaseModel):
    place_name: str
    place_id: str
    address: str | None = None
    rating: float | None = None
    review_text: str
    review_rating: int | None = None
    author: str | None = None
    lead_fit: LeadFit
    reason: str
    suggested_pitch: str | None = None


class SearchResponse(BaseModel):
    center: GeoPoint
    radius_km: float
    business_type: str
    project_id: str | None = None
    project_name: str | None = None
    places_scanned: int
    reviews_analyzed: int
    leads: list[ReviewLead]
    summary: str
