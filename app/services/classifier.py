import json

from openai import AsyncOpenAI

from app.config import settings
from app.models.schemas import LeadFit, ReviewLead

SYSTEM_PROMPT = """Eres un analista de ventas B2B. Clasificas reseñas de Google para detectar
oportunidades comerciales según un proyecto/servicio del usuario.

Responde SOLO con JSON válido, sin markdown, con esta estructura:
{
  "lead_fit": "high" | "medium" | "low" | "none",
  "theme": "etiqueta corta del dolor en español, ej: Tiempos de espera, Mala atención, Falta de reservas",
  "reason": "explicación breve en español",
  "suggested_pitch": "mensaje corto de contacto o null si no aplica"
}

Criterios:
- high: la reseña revela un dolor o necesidad que el proyecto resuelve claramente
- medium: hay señales indirectas o contexto parcialmente alineado
- low: mención vaga, poco accionable
- none: sin relación con el proyecto

Para theme: usá 2-4 palabras, concreto y reutilizable entre reseñas similares.
"""


class ReviewClassifier:
    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY no está configurada")
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    async def classify_review(
        self,
        *,
        project_description: str,
        lead_criteria: str | None,
        place_name: str,
        place_address: str | None,
        review_text: str,
        review_rating: int | None,
    ) -> tuple[LeadFit, str, str, str | None]:
        criteria_block = f"\nCriterios adicionales: {lead_criteria}" if lead_criteria else ""
        user_content = f"""Proyecto/servicio a vender:
{project_description}
{criteria_block}

Negocio: {place_name}
Dirección: {place_address or "N/A"}
Valoración de la reseña: {review_rating if review_rating is not None else "N/A"}

Reseña:
{review_text}
"""

        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )

        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)

        fit = LeadFit(data.get("lead_fit", "none"))
        theme = (data.get("theme") or "Otro").strip()
        reason = data.get("reason", "Sin razón")
        pitch = data.get("suggested_pitch")
        return fit, theme, reason, pitch

    async def summarize_leads(
        self,
        *,
        project_description: str,
        leads: list[ReviewLead],
        places_scanned: int,
        reviews_analyzed: int,
    ) -> str:
        high = sum(1 for lead in leads if lead.lead_fit == LeadFit.HIGH)
        medium = sum(1 for lead in leads if lead.lead_fit == LeadFit.MEDIUM)

        prompt = f"""Resume en 2-3 oraciones en español los hallazgos de prospección.

Proyecto: {project_description}
Lugares analizados: {places_scanned}
Reseñas analizadas: {reviews_analyzed}
Leads high: {high}
Leads medium: {medium}
Total leads relevantes (high+medium): {high + medium}
"""

        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=0.3,
            messages=[
                {
                    "role": "system",
                    "content": "Eres un asistente de ventas. Responde de forma concisa en español.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        return (response.choices[0].message.content or "").strip()
