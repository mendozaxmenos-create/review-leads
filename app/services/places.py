import json
from typing import Any

import httpx

from app.config import settings

PLACES_BASE = "https://places.googleapis.com/v1"
FIELD_MASK_SEARCH = "places.id,places.displayName,places.formattedAddress,places.rating"
FIELD_MASK_DETAILS = (
    "id,displayName,formattedAddress,rating,"
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
    def extract_contacts(place: dict[str, Any]) -> dict[str, str | None]:
        phone = place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber")
        return {
            "phone": phone,
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
