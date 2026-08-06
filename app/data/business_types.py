BUSINESS_TYPE_LABELS: dict[str, str] = {
    "restaurant": "Restaurantes",
    "cafe": "Cafés",
    "hair_salon": "Peluquerías",
    "spa": "Spas",
    "dentist": "Dentistas",
    "gym": "Gimnasios",
    "store": "Tiendas",
    "real_estate_agency": "Inmobiliarias",
    "lawyer": "Abogados",
    "accounting": "Contadores",
    "bakery": "Panaderías",
    "car_dealer": "Concesionarios",
    "insurance_agency": "Seguros",
    "doctor": "Médicos",
    "hospital": "Hospitales",
    # Alojamiento turístico
    "lodging": "Alojamiento",
    "hotel": "Hoteles",
    "guest_house": "Casas de huéspedes",
    "motel": "Moteles",
    "hostel": "Hostels",
    "resort_hotel": "Resorts",
    "campground": "Camping",
    "bed_and_breakfast": "Bed & Breakfast",
    "cottage": "Cabañas",
    "extended_stay_hotel": "Apart-hoteles",
}


# Tipos Google Places para modo alojamiento (cabañas / complejos / hoteles).
LODGING_GOOGLE_TYPES: list[str] = [
    "lodging",
    "hotel",
    "guest_house",
    "cottage",
    "motel",
    "hostel",
    "resort_hotel",
    "bed_and_breakfast",
    "extended_stay_hotel",
    "campground",
]

# Búsquedas por texto (Argentina): cubren cabañas y complejos que Google tipifica mal.
LODGING_TEXT_QUERIES: list[str] = [
    "cabañas",
    "cabaña",
    "complejo de cabañas",
    "complejo de departamentos",
    "departamentos temporarios",
    "alquiler temporario",
    "apart hotel",
    "hostel",
]

# Foco cabañas (etapa Villa Oliva): prioriza cabañas/complejos sobre hotel genérico.
CABANAS_GOOGLE_TYPES: list[str] = [
    "cottage",
    "guest_house",
    "lodging",
    "campground",
    "bed_and_breakfast",
    "extended_stay_hotel",
]

CABANAS_TEXT_QUERIES: list[str] = [
    "cabañas",
    "cabaña",
    "complejo de cabañas",
    "cabañas con pileta",
    "alquiler cabañas",
    "complejo turístico",
    "departamentos temporarios",
    "alquiler temporario",
]


SEARCH_FOCUSES: dict[str, dict] = {
    "all": {
        "id": "all",
        "label": "Todos los rubros",
        "description": "Prospección general en la zona",
        "google_types": None,  # usa all_searchable_types()
        "text_queries": [],
    },
    "lodging": {
        "id": "lodging",
        "label": "Alojamiento turístico",
        "description": "Cabañas, complejos de departamentos, hoteles, hostels y similares",
        "google_types": LODGING_GOOGLE_TYPES,
        "text_queries": LODGING_TEXT_QUERIES,
    },
    "cabanas": {
        "id": "cabanas",
        "label": "Cabañas y complejos",
        "description": "Cabañas, complejos y alquiler temporario (ideal bot de reservas)",
        "google_types": CABANAS_GOOGLE_TYPES,
        "text_queries": CABANAS_TEXT_QUERIES,
    },
}


def label_for(business_type: str) -> str:
    return BUSINESS_TYPE_LABELS.get(business_type, business_type.replace("_", " ").title())


def all_searchable_types() -> list[str]:
    """Rubros del discovery general (incluye lodging/hotel, no todos los subtipos)."""
    lodging_subtypes = set(LODGING_GOOGLE_TYPES) - {"lodging", "hotel"}
    return [key for key in BUSINESS_TYPE_LABELS if key not in lodging_subtypes]


def list_search_focuses() -> list[dict]:
    return [
        {
            "id": focus["id"],
            "label": focus["label"],
            "description": focus["description"],
        }
        for focus in SEARCH_FOCUSES.values()
    ]


def resolve_search_focus(focus_id: str | None) -> dict:
    if not focus_id or focus_id not in SEARCH_FOCUSES:
        return SEARCH_FOCUSES["all"]
    return SEARCH_FOCUSES[focus_id]
