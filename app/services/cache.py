import hashlib
import json
from typing import Any

from app.models.schemas import SearchRequest


def make_search_cache_key(request: SearchRequest) -> str:
    payload = request.model_dump(mode="json")
    center = payload.get("center", {})
    center["lat"] = round(float(center.get("lat", 0)), 4)
    center["lng"] = round(float(center.get("lng", 0)), 4)
    payload["center"] = center
    payload.pop("use_cache", None)
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def attach_saved_lead_meta(response: dict[str, Any], saved_meta: dict[str, dict[str, Any]]) -> None:
    for lead in response.get("leads", []):
        meta = saved_meta.get(lead.get("place_id", ""))
        if meta:
            lead["saved_lead_id"] = meta["saved_lead_id"]
            lead["status"] = meta["status"]
            lead["notes"] = meta["notes"]
