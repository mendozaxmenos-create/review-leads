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
}


def label_for(business_type: str) -> str:
    return BUSINESS_TYPE_LABELS.get(business_type, business_type.replace("_", " ").title())


def all_searchable_types() -> list[str]:
    return list(BUSINESS_TYPE_LABELS.keys())
