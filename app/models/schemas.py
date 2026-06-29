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


class GeocodeSuggestion(BaseModel):
    label: str
    lat: float
    lng: float
    zoom: int = 12
    kind: str = "place"
    source: str = "nominatim"


class LocationPresetOut(BaseModel):
    id: str
    label: str
    lat: float
    lng: float
    zoom: int
    kind: str
    group: str


class ServiceProfileOut(BaseModel):
    id: str
    name: str
    description: str
    lead_criteria: str
    suggested_business_types: list[str]
    is_custom: bool = False


class CustomProjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    description: str = Field(..., min_length=10)
    lead_criteria: str = Field(..., min_length=10)
    suggested_business_types: list[str] = Field(default_factory=list)


class CustomProjectUpdate(CustomProjectCreate):
    pass


class SearchRequest(BaseModel):
    """Busca negocios cercanos en todos los rubros y clasifica leads con detección automática de servicio."""

    center: GeoPoint
    radius_km: float = Field(..., gt=0, le=50, description="Radio de búsqueda en kilómetros")
    business_type: str | None = Field(
        default=None,
        description="Opcional: limitar a un rubro. null = buscar en todos los rubros",
    )
    max_places: int = Field(default=24, ge=1, le=60)
    project_id: str | None = Field(
        default=None,
        description="Opcional: filtrar solo leads de un servicio (modo legacy)",
    )
    project_description: str | None = Field(
        default=None,
        min_length=10,
        description="Descripción custom (modo legacy)",
    )
    lead_criteria: str | None = Field(
        default=None,
        description="Criterios adicionales opcionales",
    )
    max_review_rating: int | None = Field(
        default=3,
        ge=1,
        le=5,
        description="Solo analizar reseñas con rating <= este valor. null = analizar todas",
    )
    max_place_rating: float | None = Field(
        default=None,
        ge=1,
        le=5,
        description="Solo negocios con rating <= este valor. null = sin filtro",
    )
    max_reviews_per_place: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Máximo de reseñas a clasificar con IA por negocio (prioriza las peores)",
    )
    use_cache: bool = Field(default=True, description="Usar caché local de búsquedas recientes")


class ReviewSnippet(BaseModel):
    text: str
    rating: int | None = None
    author: str | None = None
    theme: str | None = None


class ReviewLead(BaseModel):
    place_name: str
    place_id: str
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
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
    solution_value: str | None = None
    business_type: str | None = None
    business_type_label: str | None = None
    recommended_project_id: str | None = None
    recommended_project_name: str | None = None
    saved_lead_id: int | None = None
    status: str | None = None
    notes: str | None = None


class CategorySuggestion(BaseModel):
    business_type: str
    business_type_label: str
    project_id: str
    project_name: str
    places_in_area: int
    reason: str
    score: float = Field(..., ge=0, le=1)


class RubroSummary(BaseModel):
    business_type: str
    business_type_label: str
    leads_count: int


class SearchResponse(BaseModel):
    center: GeoPoint
    radius_km: float
    business_type: str = "all"
    project_id: str | None = None
    project_name: str | None = "Detección automática"
    discovery_mode: bool = True
    places_scanned: int
    reviews_fetched: int = 0
    reviews_classified: int = 0
    reviews_skipped: int = 0
    reviews_analyzed: int = 0
    from_cache: bool = False
    search_history_id: int | None = None
    leads: list[ReviewLead]
    summary: str
    rubro_summary: list[RubroSummary] = []
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
    recommended_project_id: str | None = None
    business_type_label: str | None = None


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


class LeadStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    RESPONDED = "responded"
    CLOSED = "closed"
    DISCARDED = "discarded"


class LeadStatusInfo(BaseModel):
    code: int
    value: str
    label: str


class SavedLeadUpdate(BaseModel):
    status: LeadStatus | None = None
    notes: str | None = None


class SavedLeadOut(BaseModel):
    id: int
    place_id: str
    status: str
    status_code: int
    status_label: str
    notes: str | None = None
    updated_at: str
    lead: ReviewLead


class AdminLeadOut(SavedLeadOut):
    project_id: str | None = None
    project_name: str | None = None
    business_type: str | None = None
    search_at: str | None = None


class AdminStatsOut(BaseModel):
    total: int
    by_status: dict[str, int]
    by_status_code: dict[int, int]


class SearchHistoryItem(BaseModel):
    id: int
    created_at: str
    project_id: str | None = None
    project_name: str | None = None
    business_type: str
    center_lat: float
    center_lng: float
    radius_km: float
    places_scanned: int
    leads_count: int
    from_cache: bool
