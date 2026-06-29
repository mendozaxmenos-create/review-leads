"""Filtros para excluir lugares que no son prospectables B2B."""

EXCLUDED_GOOGLE_TYPES = frozenset(
    {
        "local_government_office",
        "government_office",
        "city_hall",
        "courthouse",
        "police",
        "fire_station",
        "post_office",
        "embassy",
        "military_base",
        "public_bathroom",
        "school",
        "primary_school",
        "secondary_school",
        "university",
    }
)

EXCLUDED_NAME_KEYWORDS = (
    "comisaría",
    "comisaria",
    "policía",
    "policia",
    "municipalidad",
    "municipio",
    "gobierno",
    "ministerio",
    "juzgado",
    "registro civil",
    "defensoría",
    "defensoria",
    "poder judicial",
    "gendarmería",
    "gendarmeria",
    "prefectura",
    "tribunal",
    "intendencia",
    "dirección general",
    "direccion general",
    "oficina de gobierno",
    "estación de policía",
    "estacion de policia",
)

EXCLUDED_RUBRO_KEYWORDS = (
    "gobierno",
    "policía",
    "policia",
    "comisaría",
    "comisaria",
    "municipal",
    "oficina judicial",
    "poder judicial",
    "organismo público",
    "organismo publico",
    "servicio público",
    "servicio publico",
    "entidad estatal",
    "administración pública",
    "administracion publica",
)

# Rubros comerciales privados: no deben quedar excluidos por palabras ambiguas en EXCLUDED_RUBRO_KEYWORDS.
PROSPECTABLE_RUBRO_ALLOWLIST = (
    "abogado",
    "abogados",
    "estudio jurídico",
    "estudio juridico",
    "estudio legal",
    "bufete",
    "despacho",
)


def is_prospectable_place(
    place_name: str,
    *,
    primary_type: str | None = None,
    types: list[str] | None = None,
) -> bool:
    name = (place_name or "").lower()
    if any(keyword in name for keyword in EXCLUDED_NAME_KEYWORDS):
        return False

    all_types = set(types or [])
    if primary_type:
        all_types.add(primary_type)
    if all_types & EXCLUDED_GOOGLE_TYPES:
        return False

    return True


def is_prospectable_rubro(rubro: str) -> bool:
    label = (rubro or "").lower()
    if any(keyword in label for keyword in PROSPECTABLE_RUBRO_ALLOWLIST):
        return True
    return not any(keyword in label for keyword in EXCLUDED_RUBRO_KEYWORDS)
