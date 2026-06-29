from dataclasses import dataclass


@dataclass(frozen=True)
class LocationPreset:
    id: str
    label: str
    lat: float
    lng: float
    zoom: int
    kind: str  # province | department | city | neighborhood


AR_PROVINCES: list[LocationPreset] = [
    LocationPreset("ar-ba", "Buenos Aires (CABA)", -34.6037, -58.3816, 12, "city"),
    LocationPreset("ar-pba", "Buenos Aires (provincia)", -36.0, -60.0, 8, "province"),
    LocationPreset("ar-cat", "Catamarca", -28.4696, -65.7795, 10, "province"),
    LocationPreset("ar-cha", "Chaco", -27.4510, -58.9867, 9, "province"),
    LocationPreset("ar-chu", "Chubut", -43.3002, -65.1023, 8, "province"),
    LocationPreset("ar-cba", "Córdoba (provincia)", -32.25, -63.7, 8, "province"),
    LocationPreset("ar-cba-cap", "Córdoba (capital)", -31.4201, -64.1888, 12, "city"),
    LocationPreset("ar-cor", "Corrientes", -27.4692, -58.8306, 10, "province"),
    LocationPreset("ar-eri", "Entre Ríos", -31.7310, -60.5238, 9, "province"),
    LocationPreset("ar-for", "Formosa", -26.1775, -58.1781, 10, "province"),
    LocationPreset("ar-juj", "Jujuy", -24.1858, -65.2995, 10, "province"),
    LocationPreset("ar-lp", "La Pampa", -36.6167, -64.2833, 8, "province"),
    LocationPreset("ar-lr", "La Rioja", -29.4131, -66.8558, 10, "province"),
    LocationPreset("ar-men", "Mendoza (provincia)", -34.5970, -68.7305, 8, "province"),
    LocationPreset("ar-men-cap", "Mendoza (capital)", -32.8894, -68.8446, 12, "city"),
    LocationPreset("ar-mis", "Misiones", -26.8083, -54.3086, 9, "province"),
    LocationPreset("ar-neu", "Neuquén", -38.9516, -68.0591, 10, "province"),
    LocationPreset("ar-rn", "Río Negro", -40.8135, -63.0000, 8, "province"),
    LocationPreset("ar-sal", "Salta", -24.7821, -65.4232, 11, "province"),
    LocationPreset("ar-sj", "San Juan", -31.5375, -68.5364, 11, "province"),
    LocationPreset("ar-sl", "San Luis", -33.3017, -66.3378, 10, "province"),
    LocationPreset("ar-sc", "Santa Cruz", -48.8153, -69.6140, 7, "province"),
    LocationPreset("ar-sf", "Santa Fe (provincia)", -31.0, -61.0, 8, "province"),
    LocationPreset("ar-sf-cap", "Santa Fe (capital)", -31.6333, -60.7000, 12, "city"),
    LocationPreset("ar-sde", "Santiago del Estero", -27.7951, -64.2615, 10, "province"),
    LocationPreset("ar-tf", "Tierra del Fuego", -54.8019, -68.3030, 8, "province"),
    LocationPreset("ar-tuc", "Tucumán", -26.8083, -65.2176, 11, "province"),
]

MENDOZA_DEPARTMENTS: list[LocationPreset] = [
    LocationPreset("men-capital", "Mendoza · Capital", -32.8894, -68.8446, 13, "department"),
    LocationPreset("men-godoy", "Mendoza · Godoy Cruz", -32.9236, -68.8440, 13, "department"),
    LocationPreset("men-guay", "Mendoza · Guaymallén", -32.8833, -68.8000, 13, "department"),
    LocationPreset("men-las-heras", "Mendoza · Las Heras", -32.8500, -68.8333, 12, "department"),
    LocationPreset("men-lujan", "Mendoza · Luján de Cuyo", -33.0333, -68.8833, 12, "department"),
    LocationPreset("men-maipu", "Mendoza · Maipú", -32.9667, -68.7667, 13, "department"),
    LocationPreset("men-san-martin", "Mendoza · San Martín", -33.0833, -68.4667, 12, "department"),
    LocationPreset("men-tunuyan", "Mendoza · Tunuyán", -33.5833, -69.0167, 11, "department"),
    LocationPreset("men-tupungato", "Mendoza · Tupungato", -33.3667, -69.1500, 11, "department"),
    LocationPreset("men-san-rafael", "Mendoza · San Rafael", -34.6177, -68.3301, 11, "department"),
]

ALL_PRESETS: list[LocationPreset] = AR_PROVINCES + MENDOZA_DEPARTMENTS


def match_presets(query: str, *, limit: int = 8) -> list[LocationPreset]:
    q = _normalize(query)
    if not q:
        return []

    scored: list[tuple[int, LocationPreset]] = []
    for preset in ALL_PRESETS:
        label = _normalize(preset.label)
        name_part = _normalize(preset.label.split("·")[-1])
        score = 0
        if q == name_part or q == _normalize(preset.label.split("(")[0].strip()):
            score = 100
        elif label.startswith(q) or name_part.startswith(q):
            score = 80
        elif q in label or q in name_part:
            score = 60
        elif all(part in label for part in q.split()):
            score = 50
        if score:
            if preset.kind == "city":
                score += 5
            elif preset.kind == "department":
                score += 3
            scored.append((score, preset))

    scored.sort(key=lambda item: (-item[0], item[1].label))
    seen: set[str] = set()
    results: list[LocationPreset] = []
    for _, preset in scored:
        if preset.id in seen:
            continue
        seen.add(preset.id)
        results.append(preset)
        if len(results) >= limit:
            break
    return results


def _normalize(text: str) -> str:
    import unicodedata

    text = unicodedata.normalize("NFD", text.lower().strip())
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
