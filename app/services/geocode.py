import httpx

from app.config import settings
from app.data.ar_locations import ALL_PRESETS, LocationPreset, match_presets

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

_KIND_ZOOM = {
    "house": 16,
    "building": 16,
    "residential": 15,
    "road": 15,
    "neighbourhood": 14,
    "suburb": 13,
    "quarter": 13,
    "city": 12,
    "town": 12,
    "village": 13,
    "municipality": 11,
    "county": 10,
    "state": 8,
    "province": 8,
    "region": 8,
    "country": 6,
}


class GeocodeService:
    async def search(self, query: str, *, limit: int = 8) -> list[dict]:
        query = query.strip()
        if len(query) < 2:
            return []

        results: list[dict] = []
        seen: set[str] = set()

        for preset in match_presets(query, limit=limit):
            item = _preset_to_dict(preset)
            key = f"{item['lat']:.4f},{item['lng']:.4f}"
            if key not in seen:
                seen.add(key)
                results.append(item)

        remaining = max(0, limit - len(results))
        if remaining:
            extra_rows: list[dict] = []
            try:
                extra_rows = await self._nominatim_search(query, limit=remaining + 4)
            except Exception:
                extra_rows = []
            if not extra_rows:
                extra_rows = await self._google_geocode_search(query, limit=remaining + 4)
            for item in extra_rows:
                key = f"{item['lat']:.4f},{item['lng']:.4f}"
                if key in seen:
                    continue
                seen.add(key)
                results.append(item)
                if len(results) >= limit:
                    break

        if not results:
            return []

        return self._rank_results(query, results)[:limit]

    async def _nominatim_search(self, query: str, *, limit: int) -> list[dict]:
        params = {
            "format": "jsonv2",
            "q": query,
            "countrycodes": "ar",
            "addressdetails": 1,
            "limit": str(limit),
            "accept-language": "es",
        }
        headers = {
            "User-Agent": _nominatim_user_agent(),
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.get(NOMINATIM_URL, params=params, headers=headers)
            response.raise_for_status()
            rows = response.json()

        parsed: list[dict] = []
        for row in rows:
            try:
                lat = float(row["lat"])
                lng = float(row["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            kind = row.get("addresstype") or row.get("type") or "place"
            parsed.append(
                {
                    "label": row.get("display_name", query),
                    "lat": lat,
                    "lng": lng,
                    "zoom": _zoom_for_kind(kind),
                    "kind": kind,
                    "source": "nominatim",
                    "importance": float(row.get("importance") or 0),
                }
            )
        return parsed

    async def _google_geocode_search(self, query: str, *, limit: int) -> list[dict]:
        api_key = settings.google_places_api_key.strip()
        if not api_key:
            return []

        params = {
            "address": f"{query}, Argentina",
            "key": api_key,
            "region": "ar",
            "language": "es",
        }
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.get(
                "https://maps.googleapis.com/maps/api/geocode/json",
                params=params,
            )
            response.raise_for_status()
            payload = response.json()

        if payload.get("status") not in {"OK", "ZERO_RESULTS"}:
            return []

        parsed: list[dict] = []
        for row in payload.get("results", [])[:limit]:
            location = row.get("geometry", {}).get("location", {})
            try:
                lat = float(location["lat"])
                lng = float(location["lng"])
            except (KeyError, TypeError, ValueError):
                continue
            types = row.get("types") or []
            kind = types[0] if types else "place"
            parsed.append(
                {
                    "label": row.get("formatted_address", query),
                    "lat": lat,
                    "lng": lng,
                    "zoom": _zoom_for_google_type(types),
                    "kind": kind,
                    "source": "google",
                    "importance": 0.9,
                }
            )
        return parsed

    def _rank_results(self, query: str, results: list[dict]) -> list[dict]:
        q = _normalize(query)

        def score(item: dict) -> float:
            label = _normalize(item.get("label", ""))
            base = float(item.get("importance", 0))
            if item.get("source") == "preset":
                base += 2.0
            if label.startswith(q):
                base += 1.5
            elif q in label:
                base += 0.8

            kind = item.get("kind", "")
            if len(q.split()) <= 2:
                if kind in {"city", "town", "department"}:
                    base += 1.2
                elif kind in {"state", "province", "region"}:
                    base -= 0.3

            if kind in {"house", "building", "road", "residential"}:
                base += 0.4
            return base

        return sorted(results, key=score, reverse=True)


def _preset_to_dict(preset: LocationPreset) -> dict:
    return {
        "label": preset.label,
        "lat": preset.lat,
        "lng": preset.lng,
        "zoom": preset.zoom,
        "kind": preset.kind,
        "source": "preset",
        "importance": 1.0,
    }


def _zoom_for_kind(kind: str) -> int:
    return _KIND_ZOOM.get(kind, 12)


def _zoom_for_google_type(types: list[str]) -> int:
    for kind in types:
        if kind in _KIND_ZOOM:
            return _KIND_ZOOM[kind]
    if "locality" in types:
        return 12
    if "administrative_area_level_2" in types:
        return 11
    if "administrative_area_level_1" in types:
        return 8
    return 14


def _nominatim_user_agent() -> str:
    contact = settings.nominatim_contact_email.strip() or "https://review-leads.fly.dev"
    return f"ReviewLeads/1.0 ({contact})"


def _normalize(text: str) -> str:
    import unicodedata

    text = unicodedata.normalize("NFD", text.lower().strip())
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
