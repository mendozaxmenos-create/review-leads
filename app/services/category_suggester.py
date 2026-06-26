import json

from openai import AsyncOpenAI

from app.config import settings
from app.data.business_types import label_for
from app.data.services import SERVICE_PROFILES, get_profile
from app.models.schemas import CategorySuggestion, GeoPoint
from app.services.places import PlacesService


class CategorySuggester:
    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    async def suggest(
        self,
        *,
        center: GeoPoint,
        radius_km: float,
        current_business_type: str,
        project_id: str | None,
        project_description: str,
        places_found: int,
        relevant_leads: int,
    ) -> list[CategorySuggestion]:
        profile = get_profile(project_id) if project_id else None
        suggested_for_service = profile.suggested_business_types if profile else []
        category_mismatch = bool(suggested_for_service and current_business_type not in suggested_for_service)
        few_leads = relevant_leads < 2

        if not category_mismatch and not few_leads and places_found > 0:
            return []

        places_service = PlacesService()
        types_to_probe: list[str] = []

        if profile:
            types_to_probe.extend(t for t in profile.suggested_business_types if t != current_business_type)
        else:
            types_to_probe.extend(
                t for profile in SERVICE_PROFILES for t in profile.suggested_business_types
            )

        seen: set[str] = {current_business_type}
        probe_results: list[dict[str, object]] = []

        for business_type in types_to_probe:
            if business_type in seen:
                continue
            seen.add(business_type)
            try:
                places = await places_service.search_nearby(
                    lat=center.lat,
                    lng=center.lng,
                    radius_km=radius_km,
                    business_type=business_type,
                    max_results=5,
                )
            except Exception:
                continue
            if places:
                probe_results.append(
                    {
                        "business_type": business_type,
                        "label": label_for(business_type),
                        "places_in_area": len(places),
                    }
                )

        if not probe_results and category_mismatch and suggested_for_service:
            return [
                CategorySuggestion(
                    business_type=t,
                    business_type_label=label_for(t),
                    project_id=project_id or "",
                    project_name=profile.name if profile else "Tu servicio",
                    places_in_area=0,
                    reason=(
                        f"'{label_for(current_business_type)}' no es la categoría ideal para "
                        f"{profile.name if profile else 'este servicio'}. Probá buscar {label_for(t)}."
                    ),
                    score=0.9 - idx * 0.1,
                )
                for idx, t in enumerate(suggested_for_service[:3])
                if t != current_business_type
            ]

        if not probe_results:
            return []

        ranked = await self._rank_with_llm(
            current_business_type=current_business_type,
            project_description=project_description,
            project_name=profile.name if profile else "Servicio custom",
            project_id=project_id or "custom",
            probe_results=probe_results,
            places_found=places_found,
            relevant_leads=relevant_leads,
            category_mismatch=category_mismatch,
        )
        return ranked[:5]

    async def _rank_with_llm(
        self,
        *,
        current_business_type: str,
        project_description: str,
        project_name: str,
        project_id: str,
        probe_results: list[dict[str, object]],
        places_found: int,
        relevant_leads: int,
        category_mismatch: bool,
    ) -> list[CategorySuggestion]:
        prompt = f"""Servicio a vender: {project_name}
Descripción: {project_description}
Categoría buscada ahora: {label_for(current_business_type)} ({current_business_type})
Lugares encontrados: {places_found}
Leads relevantes (high+medium): {relevant_leads}
¿Categoría desalineada con el servicio?: {category_mismatch}

Categorías alternativas con negocios en la zona:
{json.dumps(probe_results, ensure_ascii=False)}

Todos los servicios disponibles:
{json.dumps([{"id": p.id, "name": p.name, "types": p.suggested_business_types} for p in SERVICE_PROFILES], ensure_ascii=False)}

Devolvé JSON:
{{
  "suggestions": [
    {{
      "business_type": "tipo_google",
      "project_id": "id_servicio o el actual",
      "reason": "por qué conviene en español",
      "score": 0.0-1.0
    }}
  ]
}}
Máximo 5 sugerencias, ordenadas por score descendente.
Si la categoría actual no encaja, priorizá alternativas con más negocios y mejor fit.
"""

        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "Sos consultor de prospección B2B. Respondé solo JSON válido en español.",
                },
                {"role": "user", "content": prompt},
            ],
        )

        raw = response.choices[0].message.content or '{"suggestions":[]}'
        data = json.loads(raw)
        suggestions: list[CategorySuggestion] = []

        counts = {str(r["business_type"]): int(r["places_in_area"]) for r in probe_results}

        for item in data.get("suggestions", []):
            btype = item.get("business_type", "")
            if not btype:
                continue
            pid = item.get("project_id") or project_id
            pname = project_name
            alt_profile = get_profile(pid)
            if alt_profile:
                pname = alt_profile.name

            suggestions.append(
                CategorySuggestion(
                    business_type=btype,
                    business_type_label=label_for(btype),
                    project_id=pid,
                    project_name=pname,
                    places_in_area=counts.get(btype, 0),
                    reason=item.get("reason", "Mejor encaje para tu servicio en esta zona."),
                    score=float(item.get("score", 0.5)),
                )
            )

        suggestions.sort(key=lambda s: s.score, reverse=True)
        return suggestions
