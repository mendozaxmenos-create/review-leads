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

# Base Córdoba v1: Punilla + Calamuchita (misma campaña, base_name=Córdoba).
CORDOBA_CABANAS_ZONES: list[CampaignZone] = [
    # Valle de Punilla
    CampaignZone("cba-carlos-paz", "Villa Carlos Paz", -31.4241, -64.4974, 14, 12),
    CampaignZone("cba-cosquin", "Cosquín", -31.2450, -64.4650, 12, 12),
    CampaignZone("cba-la-falda", "La Falda", -31.0936, -64.4828, 12, 12),
    CampaignZone("cba-la-cumbre", "La Cumbre", -30.9822, -64.4911, 12, 12),
    CampaignZone("cba-capilla", "Capilla del Monte", -30.8567, -64.5261, 12, 12),
    CampaignZone("cba-valle-hermoso", "Valle Hermoso / Huerta Grande", -31.0950, -64.4850, 12, 12),
    # Valle de Calamuchita
    CampaignZone("cba-vgb", "Villa General Belgrano", -31.9767, -64.5603, 14, 12),
    CampaignZone("cba-santa-rosa", "Santa Rosa de Calamuchita", -32.0667, -64.5333, 14, 12),
    CampaignZone("cba-embalse", "Embalse / Villa Rumipal", -32.2000, -64.4333, 14, 11),
    CampaignZone("cba-los-reartes", "Los Reartes / Villa Berna", -31.9100, -64.6500, 12, 12),
    CampaignZone("cba-cumbrecita", "La Cumbrecita", -31.8972, -64.7722, 10, 13),
]

# --- Ola 1 expansión AR (cabañas / complejos) ---

BUENOS_AIRES_INTERIOR_CABANAS_ZONES: list[CampaignZone] = [
    CampaignZone("ba-tandil", "Tandil", -37.3217, -59.1332, 14, 12),
    CampaignZone("ba-sierra-ventana", "Sierra de la Ventana", -38.1367, -61.7933, 14, 12),
    CampaignZone("ba-villa-ventana", "Villa Ventana", -38.0833, -61.9333, 12, 12),
]

SAN_LUIS_CABANAS_ZONES: list[CampaignZone] = [
    CampaignZone("sl-trapiche", "El Trapiche", -33.1167, -66.0667, 12, 12),
    CampaignZone("sl-merlo", "Merlo", -32.3428, -65.0139, 14, 12),
    CampaignZone("sl-potrero", "Potrero de los Funes", -33.2167, -66.2333, 12, 12),
]

SALTA_CABANAS_ZONES: list[CampaignZone] = [
    CampaignZone("sal-cafayate", "Cafayate", -26.0728, -65.9761, 14, 12),
    CampaignZone("sal-cachi", "Cachi", -25.1200, -66.1650, 12, 12),
    CampaignZone("sal-san-lorenzo", "San Lorenzo / cerros Salta", -24.7280, -65.4860, 12, 12),
]

JUJUY_CABANAS_ZONES: list[CampaignZone] = [
    CampaignZone("juj-purmamarca", "Purmamarca", -23.7458, -65.4992, 12, 12),
    CampaignZone("juj-tilcara", "Tilcara", -23.5767, -65.3506, 12, 12),
    CampaignZone("juj-humahuaca", "Humahuaca", -23.2056, -65.3503, 12, 12),
]

NEUQUEN_CABANAS_ZONES: list[CampaignZone] = [
    CampaignZone("nq-sma", "San Martín de los Andes", -40.1579, -71.3534, 14, 12),
    CampaignZone("nq-vla", "Villa La Angostura", -40.7617, -71.6464, 14, 12),
    CampaignZone("nq-traful", "Villa Traful", -40.6583, -71.4000, 12, 12),
]

RIO_NEGRO_CABANAS_ZONES: list[CampaignZone] = [
    CampaignZone("rn-bariloche", "Bariloche (centro)", -41.1335, -71.3103, 14, 12),
    CampaignZone("rn-circuito-chico", "Bariloche · Circuito Chico", -41.0833, -71.5333, 12, 12),
    CampaignZone("rn-el-bolson", "El Bolsón", -41.9667, -71.5167, 14, 12),
    CampaignZone("rn-las-grutas", "Las Grutas", -40.8028, -65.0778, 12, 12),
]

# --- Ola 2 ---
CATAMARCA_CABANAS_ZONES: list[CampaignZone] = [
    CampaignZone("cat-fiambala", "Fiambalá", -27.6889, -67.6167, 12, 12),
    CampaignZone("cat-belen", "Belén", -27.6500, -67.0333, 12, 12),
    CampaignZone("cat-tinogasta", "Tinogasta", -28.0667, -67.5667, 12, 12),
]

LA_RIOJA_CABANAS_ZONES: list[CampaignZone] = [
    CampaignZone("lr-chilecito", "Chilecito", -29.1667, -67.5000, 14, 12),
    CampaignZone("lr-villa-union", "Villa Unión", -29.3167, -68.2167, 12, 12),
    CampaignZone("lr-nonogasta", "Nonogasta / costa riojana", -29.3000, -67.5000, 12, 12),
]

ENTRE_RIOS_CABANAS_ZONES: list[CampaignZone] = [
    CampaignZone("er-colon", "Colón", -32.2236, -58.1442, 14, 12),
    CampaignZone("er-gualeguaychu", "Gualeguaychú", -33.0094, -58.5172, 14, 12),
    CampaignZone("er-federacion", "Federación", -30.9833, -57.9167, 12, 12),
]

MISIONES_INTERIOR_CABANAS_ZONES: list[CampaignZone] = [
    CampaignZone("mis-aristobulo", "Aristóbulo del Valle", -27.0967, -54.8967, 12, 12),
    CampaignZone("mis-el-soberbio", "El Soberbio", -27.2950, -54.1983, 12, 12),
    CampaignZone("mis-san-ignacio", "San Ignacio", -27.2583, -55.5333, 12, 12),
]

CHUBUT_CABANAS_ZONES: list[CampaignZone] = [
    CampaignZone("chu-esquel", "Esquel", -42.9097, -71.3195, 14, 12),
    CampaignZone("chu-trevelin", "Trevelin", -43.0833, -71.4667, 12, 12),
    CampaignZone("chu-cholila", "Cholila / Lago Puelo", -42.5167, -71.4667, 12, 12),
]

SANTA_CRUZ_CABANAS_ZONES: list[CampaignZone] = [
    CampaignZone("sc-calafate", "El Calafate", -50.3379, -72.2648, 14, 12),
    CampaignZone("sc-chalten", "El Chaltén", -49.3315, -72.8864, 14, 12),
]

TIERRA_DEL_FUEGO_CABANAS_ZONES: list[CampaignZone] = [
    CampaignZone("tdf-ushuaia", "Ushuaia", -54.8019, -68.3030, 14, 12),
    CampaignZone("tdf-tolhuin", "Tolhuin", -54.5167, -67.2000, 12, 12),
]

# Registro de bases CRM → zonas (incluye Mendoza/Córdoba para CLI genérico).
CABANAS_BASES: dict[str, list[CampaignZone]] = {
    "Mendoza": MENDOZA_CABANAS_ZONES,
    "Córdoba": CORDOBA_CABANAS_ZONES,
    "Buenos Aires (interior)": BUENOS_AIRES_INTERIOR_CABANAS_ZONES,
    "San Luis": SAN_LUIS_CABANAS_ZONES,
    "Salta": SALTA_CABANAS_ZONES,
    "Jujuy": JUJUY_CABANAS_ZONES,
    "Neuquén": NEUQUEN_CABANAS_ZONES,
    "Río Negro": RIO_NEGRO_CABANAS_ZONES,
    "Catamarca": CATAMARCA_CABANAS_ZONES,
    "La Rioja": LA_RIOJA_CABANAS_ZONES,
    "Entre Ríos": ENTRE_RIOS_CABANAS_ZONES,
    "Misiones (interior)": MISIONES_INTERIOR_CABANAS_ZONES,
    "Chubut": CHUBUT_CABANAS_ZONES,
    "Santa Cruz": SANTA_CRUZ_CABANAS_ZONES,
    "Tierra del Fuego": TIERRA_DEL_FUEGO_CABANAS_ZONES,
}

# Orden de barrido Ola 1 (costo Places / saturación OTA).
CABANAS_OLA1_ORDER: tuple[str, ...] = (
    "Buenos Aires (interior)",
    "San Luis",
    "Salta",
    "Jujuy",
    "Neuquén",
    "Río Negro",
)

# Ola 2: interior NOA + Litoral + Patagonia sur (sin envíos hasta validar).
CABANAS_OLA2_ORDER: tuple[str, ...] = (
    "Catamarca",
    "La Rioja",
    "Entre Ríos",
    "Misiones (interior)",
    "Chubut",
    "Santa Cruz",
    "Tierra del Fuego",
)


def list_cabanas_base_names() -> list[str]:
    return list(CABANAS_BASES.keys())


def list_cabanas_zones_for_base(base_name: str) -> list[CampaignZone]:
    key = (base_name or "").strip()
    if key in CABANAS_BASES:
        return list(CABANAS_BASES[key])
    # match casefold
    want = key.casefold()
    for name, zones in CABANAS_BASES.items():
        if name.casefold() == want:
            return list(zones)
    raise KeyError(
        f"Base desconocida: {base_name!r}. Válidas: {', '.join(CABANAS_BASES)}"
    )


def cabanas_base_center(base_name: str) -> tuple[float, float]:
    zones = list_cabanas_zones_for_base(base_name)
    if not zones:
        return (-34.0, -64.0)
    lat = sum(z.lat for z in zones) / len(zones)
    lng = sum(z.lng for z in zones) / len(zones)
    return (lat, lng)


# Mantener presets de mapa alineados con zonas nuevas de campaña.
_EXTRA_MENDOZA_PRESETS = [
    LocationPreset(z.id, f"Mendoza · {z.label}", z.lat, z.lng, z.zoom, "city")
    for z in MENDOZA_CABANAS_ZONES
    if z.id not in {p.id for p in MENDOZA_DEPARTMENTS}
]
MENDOZA_DEPARTMENTS = list(MENDOZA_DEPARTMENTS) + _EXTRA_MENDOZA_PRESETS

_EXTRA_CORDOBA_PRESETS = [
    LocationPreset(z.id, f"Córdoba · {z.label}", z.lat, z.lng, z.zoom, "city")
    for z in CORDOBA_CABANAS_ZONES
]

_EXTRA_OLA1_PRESETS = [
    LocationPreset(z.id, f"{base} · {z.label}", z.lat, z.lng, z.zoom, "city")
    for base in CABANAS_OLA1_ORDER
    for z in CABANAS_BASES[base]
]

_EXTRA_OLA2_PRESETS = [
    LocationPreset(z.id, f"{base} · {z.label}", z.lat, z.lng, z.zoom, "city")
    for base in CABANAS_OLA2_ORDER
    for z in CABANAS_BASES[base]
]

ALL_PRESETS: list[LocationPreset] = (
    AR_PROVINCES
    + MENDOZA_DEPARTMENTS
    + _EXTRA_CORDOBA_PRESETS
    + _EXTRA_OLA1_PRESETS
    + _EXTRA_OLA2_PRESETS
)


def list_mendoza_cabanas_zones() -> list[CampaignZone]:
    return list(MENDOZA_CABANAS_ZONES)


def list_cordoba_cabanas_zones() -> list[CampaignZone]:
    return list(CORDOBA_CABANAS_ZONES)


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
