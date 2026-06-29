import asyncio
import json
from typing import Any

import httpx

from app.config import settings
from app.data.business_types import all_searchable_types

PLACES_BASE = "https://places.googleapis.com/v1"
FIELD_MASK_SEARCH = (
    "places.id,places.displayName,places.formattedAddress,places.rating,places.primaryType"
)
FIELD_MASK_DETAILS = (
    "id,displayName,formattedAddress,rating,location,primaryType,types,"
    "nationalPhoneNumber,internationalPhoneNumber,websiteUri,googleMapsUri,"
    "reviews.text,reviews.rating,reviews.authorAttribution.displayName"
)


class PlacesService:
    def __init__(self) -> None:
        if not settings.google_places_api_key:
            raise ValueError("GOOGLE_PLACES_API_KEY no está configurada")

    def _headers(self, field_mask: str) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": settings.google_places_api_key,
            "X-Goog-FieldMask": field_mask,
        }

    async def search_nearby(
        self,
        lat: float,
        lng: float,
        radius_km: float,
        business_type: str,
        max_results: int,
    ) -> list[dict[str, Any]]:
        radius_m = int(radius_km * 1000)
        body = {
            "includedTypes": [business_type],
            "maxResultCount": min(max_results, 20),
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": float(radius_m),
                }
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{PLACES_BASE}/places:searchNearby",
                headers=self._headers(FIELD_MASK_SEARCH),
                json=body,
            )
            response.raise_for_status()
            data = response.json()

        return data.get("places", [])

    async def search_discovery(
        self,
        lat: float,
        lng: float,
        radius_km: float,
        max_results: int,
        business_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        types = business_types or all_searchable_types()
        per_type = max(2, min(4, max_results // max(len(types), 1) + 1))
        semaphore = asyncio.Semaphore(5)

        async def fetch_type(business_type: str) -> list[dict[str, Any]]:
            async with semaphore:
                try:
                    places = await self.search_nearby(
                        lat=lat,
                        lng=lng,
                        radius_km=radius_km,
                        business_type=business_type,
                        max_results=per_type,
                    )
                except Exception:
                    return []
                return [
                    {
                        "place": place,
                        "business_type": business_type,
                    }
                    for place in places
                ]

        batches = await asyncio.gather(*(fetch_type(bt) for bt in types))
        seen: dict[str, dict[str, Any]] = {}
        for batch in batches:
            for item in batch:
                place_id = item["place"].get("id", "")
                if place_id and place_id not in seen:
                    seen[place_id] = item

        return list(seen.values())[:max_results]

    @staticmethod
    def infer_business_type(place: dict[str, Any], fallback: str | None = None) -> str:
        primary = place.get("primaryType")
        if primary:
            return primary
        types = place.get("types") or []
        if types:
            return types[0]
        return fallback or "store"

    async def get_place_details(self, place_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{PLACES_BASE}/places/{place_id}",
                headers=self._headers(FIELD_MASK_DETAILS),
            )
            response.raise_for_status()
            return response.json()

    @staticmethod
    def place_name(place: dict[str, Any]) -> str:
        display = place.get("displayName") or {}
        return display.get("text", "Sin nombre")

    @staticmethod
    def extract_location(place: dict[str, Any]) -> tuple[float | None, float | None]:
        location = place.get("location") or {}
        lat = location.get("latitude")
        lng = location.get("longitude")
        return lat, lng

    @staticmethod
    def extract_contacts(place: dict[str, Any]) -> dict[str, str | None]:
        phone = place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber")
        return {
            "phone": phone,
            "email": None,
            "website": place.get("websiteUri"),
            "google_maps_url": place.get("googleMapsUri"),
        }

    @staticmethod
    def _localized_text(value: Any) -> str:
        if isinstance(value, dict):
            return (value.get("text") or "").strip()
        if isinstance(value, str):
            return value.strip()
        return ""

    @staticmethod
    def extract_reviews(place: dict[str, Any]) -> list[dict[str, Any]]:
        reviews = place.get("reviews") or []
        result: list[dict[str, Any]] = []
        for review in reviews:
            text = PlacesService._localized_text(review.get("text"))
            if not text:
                continue
            author = None
            attribution = review.get("authorAttribution") or {}
            if attribution.get("displayName"):
                author = attribution["displayName"]
            result.append(
                {
                    "text": text,
                    "rating": review.get("rating"),
                    "author": author,
                }
            )
        return result

    @staticmethod
    def _spanish_score(text: str) -> int:
        text_lower = text.lower()
        spanish = (
            " que ", " con ", " para ", " muy ", " mal ", " bien ", " no ", " el ", " la ",
            " los ", " las ", " es ", " está ", " esta ", " horrible ", " pésimo ", " pesimo ",
            " atención ", " atencion ", " nunca ", " siempre ", " lugar ", " servicio ",
        )
        english = (
            " the ", " and ", " very ", " bad ", " good ", " not ", " can't ", " don't ",
            " it's ", " they ", " worst ", " never ", " always ", " place ", " service ",
        )
        score = sum(1 for marker in spanish if marker in f" {text_lower} ")
        score -= sum(1 for marker in english if marker in f" {text_lower} ")
        return score

    @staticmethod
    def select_reviews_for_analysis(
        reviews: list[dict[str, Any]],
        *,
        max_review_rating: int | None,
        max_reviews_per_place: int,
    ) -> tuple[list[dict[str, Any]], int]:
        skipped = 0
        candidates = list(reviews)

        if max_review_rating is not None:
            filtered: list[dict[str, Any]] = []
            for review in candidates:
                rating = review.get("rating")
                if rating is None or rating <= max_review_rating:
                    filtered.append(review)
                else:
                    skipped += 1
            candidates = filtered

        def sort_key(review: dict[str, Any]) -> tuple[int, int]:
            rating = review.get("rating")
            rating_val = rating if rating is not None else 99
            return (rating_val, -PlacesService._spanish_score(review.get("text", "")))

        candidates.sort(key=sort_key)

        if len(candidates) > max_reviews_per_place:
            skipped += len(candidates) - max_reviews_per_place
            candidates = candidates[:max_reviews_per_place]

        return candidates, skipped
