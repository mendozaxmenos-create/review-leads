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
    LocationPreset("men-malargue", "Mendoza · Malargüe", -35.4750, -69.5850, 11, "department"),
    LocationPreset("men-potrerillos", "Mendoza · Potrerillos", -32.9667, -69.1833, 12, "city"),
    LocationPreset("men-cacheuta", "Mendoza · Cacheuta", -33.0167, -69.1167, 13, "city"),
    LocationPreset("men-uspallata", "Mendoza · Uspallata", -32.5931, -69.3469, 12, "city"),
    LocationPreset("men-valle-uco", "Mendoza · Valle de Uco (centro)", -33.5500, -69.0500, 11, "city"),
]


@dataclass(frozen=True)
class CampaignZone:
    """Zona para barridos de campaña (radio sugerido en km)."""

    id: str
    label: str
    lat: float
    lng: float
    radius_km: float = 12.0
    zoom: int = 11


# Etapa 1 Villa Oliva / bot de reservas: cabañas en zonas turísticas de Mendoza.
MENDOZA_CABANAS_ZONES: list[CampaignZone] = [
    CampaignZone("men-potrerillos", "Potrerillos", -32.9667, -69.1833, 14, 12),
    CampaignZone("men-cacheuta", "Cacheuta", -33.0167, -69.1167, 10, 13),
    CampaignZone("men-uspallata", "Uspallata", -32.5931, -69.3469, 15, 12),
    CampaignZone("men-lujan", "Luján de Cuyo / Chacras", -33.0333, -68.8833, 14, 12),
    CampaignZone("men-chacras", "Chacras de Coria", -33.0167, -68.8833, 8, 13),
    CampaignZone("men-maipu", "Maipú (ruta del vino)", -32.9667, -68.7667, 12, 12),
    CampaignZone("men-valle-uco", "Valle de Uco (centro)", -33.5500, -69.0500, 18, 11),
    CampaignZone("men-tunuyan", "Tunuyán", -33.5833, -69.0167, 14, 11),
    CampaignZone("men-tupungato", "Tupungato", -33.3667, -69.1500, 14, 11),
    CampaignZone("men-san-carlos", "San Carlos / La Consulta", -33.7667, -69.0333, 14, 11),
    CampaignZone("men-vista-flores", "Vista Flores", -33.6500, -69.1500, 10, 12),
    CampaignZone("men-san-rafael", "San Rafael", -34.6177, -68.3301, 16, 11),
    CampaignZone("men-valle-grande", "Valle Grande (San Rafael)", -34.7333, -68.1167, 14, 11),
    CampaignZone("men-los-reyunos", "Los Reyunos", -34.5833, -68.6167, 12, 12),
    CampaignZone("men-malargue", "Malargüe", -35.4750, -69.5850, 16, 11),
    CampaignZone("men-las-lenas", "Las Leñas", -35.1467, -70.0817, 12, 12),
    CampaignZone("men-los-molles", "Los Molles", -35.2000, -69.9333, 10, 12),
]

# Mantener presets de mapa alineados con zonas nuevas de campaña.
_EXTRA_MENDOZA_PRESETS = [
    LocationPreset(z.id, f"Mendoza · {z.label}", z.lat, z.lng, z.zoom, "city")
    for z in MENDOZA_CABANAS_ZONES
    if z.id not in {p.id for p in MENDOZA_DEPARTMENTS}
]
MENDOZA_DEPARTMENTS = list(MENDOZA_DEPARTMENTS) + _EXTRA_MENDOZA_PRESETS

ALL_PRESETS: list[LocationPreset] = AR_PROVINCES + MENDOZA_DEPARTMENTS


def list_mendoza_cabanas_zones() -> list[CampaignZone]:
    return list(MENDOZA_CABANAS_ZONES)


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
