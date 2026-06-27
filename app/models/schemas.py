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


class ReviewSnippet(BaseModel):
    text: str
    rating: int | None = None
    author: str | None = None
    theme: str | None = None


class ReviewLead(BaseModel):
    place_name: str
    place_id: str
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    google_maps_url: str | None = None
    rating: float | None = None
    lead_fit: LeadFit
    themes: list[str] = []
    theme_counts: dict[str, int] = {}
    reviews_count: int = 1
    review_samples: list[ReviewSnippet] = []
    review_text: str
    review_rating: int | None = None
    author: str | None = None
    reason: str
    suggested_pitch: str | None = None


class CategorySuggestion(BaseModel):
    business_type: str
    business_type_label: str
    project_id: str
    project_name: str
    places_in_area: int
    reason: str
    score: float = Field(..., ge=0, le=1)


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
    category_suggestions: list[CategorySuggestion] = []


class LeadInput(BaseModel):
    place_name: str
    place_id: str
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    themes: list[str] = []
    reviews_count: int = 1
    review_text: str
    lead_fit: str
    reason: str
    suggested_pitch: str | None = None


class MessageRequest(BaseModel):
    lead: LeadInput
    project_id: str | None = None
    project_description: str | None = None
    channel: str = Field(default="whatsapp", pattern="^(whatsapp|email|linkedin)$")


class OutreachMessage(BaseModel):
    channel: str
    subject: str | None = None
    body: str
    whatsapp_link: str | None = None
    email_link: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    tips: str | None = None


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ConversationRequest(BaseModel):
    lead: LeadInput
    project_id: str | None = None
    project_description: str | None = None
    messages: list[ChatMessage] = []


class ConversationResponse(BaseModel):
    reply: str
    stage: str
    next_action: str
    close_probability: int = Field(..., ge=0, le=100)


class BulkMessageRequest(BaseModel):
    leads: list[LeadInput]
    project_id: str | None = None
    project_description: str | None = None
    channel: str = "whatsapp"


class BulkMessageItem(BaseModel):
    place_id: str
    place_name: str
    message: OutreachMessage


class BulkMessageResponse(BaseModel):
    messages: list[BulkMessageItem]
