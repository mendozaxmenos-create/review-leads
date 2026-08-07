"""Reglas para depurar leads de cabañas / complejos (campaña Mendoza)."""

from __future__ import annotations

import re
import unicodedata

# Labels Google / nuestros que suelen ser cabaña o temporario
INCLUDE_LABELS = {
    "cabañas",
    "cabanas",
    "casas de huéspedes",
    "casas de huespedes",
    "apart-hoteles",
    "apart hoteles",
    "bed & breakfast",
    "bed and breakfast",
    "alojamiento",
}

# Labels a excluir salvo que el nombre diga cabaña/complejo
EXCLUDE_LABELS = {
    "hoteles",
    "hotels",
    "camping",
    "campings",
    "resorts",
    "hostels",
    "moteles",
}

# Cadenas / marcas urbanas que no son prospecto tipo Villa Oliva
CHAIN_KEYWORDS = (
    "amerian",
    "amérian",
    "hilton",
    "marriott",
    "ihg",
    "holiday inn",
    "sheraton",
    "hyatt",
    "novotel",
    "ibis",
    "radisson",
    "howard johnson",
    "nh hotel",
    "mercure",
    "wyndham",
    "best western",
    "crowne plaza",
    "intercontinental",
)

CABANA_NAME_HINTS = (
    "cabaña",
    "cabana",
    "cabanas",
    "cabañas",
    "complejo",
    "apart",
    "temporario",
    "temporarios",
    "lodge",
    "chalet",
    "bungalow",
    "bungalows",
    "departamentos",
    "depto",
    "deptos",
    "alquiler temporario",
    "casa de huésped",
    "guest house",
    "posada",
)

EXCLUDE_NAME_HINTS = (
    "camping",
    "campamento",
    "hostel",
    "hostal",
    "motel",
)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", (text or "").lower().strip())
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def classify_cabana_lead(row: dict) -> tuple[bool, str]:
    """
    Decide si un lead es prospecto cabaña/complejo.

    Returns:
        (ready, reason) — ready=True para enviar; reason explica la decisión.
    """
    name = (row.get("place_name") or "").strip()
    label = (row.get("business_type_label") or "").strip()
    phone = (row.get("phone") or "").strip()
    name_n = _normalize(name)
    label_n = _normalize(label)

    if not phone:
        return False, "sin_telefono"

    if any(chain in name_n for chain in CHAIN_KEYWORDS if chain):
        return False, "cadena_hotelera"

    has_cabana_name = any(h in name_n for h in CABANA_NAME_HINTS)
    has_exclude_name = any(h in name_n for h in EXCLUDE_NAME_HINTS)

    if label_n in EXCLUDE_LABELS:
        if has_cabana_name and not has_exclude_name:
            return True, "label_excluible_pero_nombre_cabana"
        if label_n in {"camping", "campings"}:
            return False, "camping"
        if label_n in {"hostels"}:
            return False, "hostel"
        if label_n in {"moteles"}:
            return False, "motel"
        if label_n in {"hoteles", "hotels", "resorts"}:
            return False, "hotel_resort"

    if has_exclude_name and not has_cabana_name:
        if "camping" in name_n or "campamento" in name_n:
            return False, "camping_en_nombre"
        if "hostel" in name_n or "hostal" in name_n:
            return False, "hostel_en_nombre"
        if "motel" in name_n:
            return False, "motel_en_nombre"

    if has_cabana_name:
        return True, "nombre_cabana_complejo"

    if label_n in INCLUDE_LABELS or label_n.startswith("alojamiento"):
        return True, "label_alojamiento_compatible"

    # Tipos genéricos residuales: solo si suena a temporario
    if re.search(r"\b(villa|finca|estancia|quinta)\b", name_n):
        return True, "nombre_rural_turistico"

    return False, "no_parece_cabana"
