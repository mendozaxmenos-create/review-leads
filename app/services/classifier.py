import json

from openai import AsyncOpenAI

from app.config import settings, outreach_sender_signature
from app.data.outreach_guidelines import FIRST_CONTACT_RULES, GOOGLE_REVIEWS_SOURCE_RULES
from app.data.services import DISCOVERY_INTRO, catalog_for_discovery, get_profile
from app.data.lead_filters import is_prospectable_rubro
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

DISCOVERY_SYSTEM_PROMPT = """Eres un analista de ventas B2B para un estudio que desarrolla soluciones digitales con Cursor (IA + código).

Tu trabajo: leer reseñas de negocios PRIVADOS/COMERCIALES locales y detectar oportunidades de venta de software.

IMPORTANTE — NO son prospectables (prospectable=false, lead_fit=none):
- Comisarías, policía, municipalidades, juzgados, organismos públicos, escuelas públicas, hospitales públicos estatales
- Cualquier entidad donde un mensaje comercial de WhatsApp no tenga sentido

SÍ son prospectables (negocios privados/comerciales), por ejemplo:
- Estudios de abogados, bufetes y despachos jurídicos
- Restaurantes, hoteles, clínicas privadas, inmobiliarias, peluquerías, gimnasios, etc.

business_rubro debe reflejar el rubro REAL del lugar (tipo Google / nombre del negocio).
Una comisaría es "Policía" o "Gobierno", NUNCA "Abogados". Un estudio jurídico privado sí es "Abogados".

Responde SOLO con JSON válido:
{
  "lead_fit": "high" | "medium" | "low" | "none",
  "prospectable": true | false,
  "theme": "etiqueta corta del dolor en español",
  "reason": "por qué es oportunidad comercial (negocio privado)",
  "recommended_service_id": "id del catálogo o null",
  "suggested_pitch": "primer contacto del vendedor AL negocio: presentación + quejas de clientes en Google + 2-3 opciones + pregunta de interés (SIN proponer reunión) o null",
  "solution_value": "2-3 oraciones: cómo la solución elegida mejora los dolores detectados",
  "business_rubro": "rubro comercial en español: Restaurante, Peluquería, Inmobiliaria (NUNCA gobierno/policía)",
  "review_text_es": "texto de la reseña en español (traducir si estaba en inglés u otro idioma)"
}

Criterios lead_fit (solo si prospectable=true):
- high: dolor claro resoluble con software/automatización/IA
- medium: señales indirectas
- low: mención vaga
- none: sin oportunidad o no prospectable

recommended_service_id: id del catálogo. Si ninguno encaja, "cursor-dev".
review_text_es: SIEMPRE en español rioplatense.
solution_value: concreto, vinculando dolores (theme) con el servicio recomendado.
suggested_pitch: seguir estas reglas de primer contacto:
""" + FIRST_CONTACT_RULES + "\n" + GOOGLE_REVIEWS_SOURCE_RULES


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

    async def classify_review_discovery(
        self,
        *,
        place_name: str,
        place_address: str | None,
        business_type_label: str,
        review_text: str,
        review_rating: int | None,
        google_primary_type: str | None = None,
    ) -> tuple[LeadFit, str, str, str | None, str | None, str, str | None, str, bool]:
        catalog = catalog_for_discovery()
        user_content = f"""{DISCOVERY_INTRO}

Catálogo de servicios (elegí recommended_service_id):
{json.dumps(catalog, ensure_ascii=False)}

Negocio contactado (destinatario): {place_name}
Rubro detectado: {business_type_label}
Tipo Google: {google_primary_type or "N/A"}
Vendedor (remitente del pitch): {outreach_sender_signature()}
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
                {"role": "system", "content": DISCOVERY_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )

        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)

        fit = LeadFit(data.get("lead_fit", "none"))
        prospectable = bool(data.get("prospectable", True))
        theme = (data.get("theme") or "Otro").strip()
        reason = data.get("reason", "Sin razón")
        pitch = data.get("suggested_pitch")
        solution_value = (data.get("solution_value") or "").strip() or None
        review_text_es = (data.get("review_text_es") or review_text).strip()
        service_id = data.get("recommended_service_id") or "cursor-dev"
        if not get_profile(service_id):
            service_id = "cursor-dev"
        rubro = (data.get("business_rubro") or business_type_label).strip()

        if not prospectable or not is_prospectable_rubro(rubro):
            return LeadFit.NONE, theme, reason, pitch, service_id, rubro, solution_value, review_text_es, False

        return fit, theme, reason, pitch, service_id, rubro, solution_value, review_text_es, True

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

        prompt = f"""Resume en 2-3 oraciones en español los hallazgos de prospección automática.

Oferta: {DISCOVERY_INTRO}
Lugares analizados: {places_scanned}
Reseñas analizadas: {reviews_analyzed}
Leads high: {high}
Leads medium: {medium}
Total leads relevantes (high+medium): {high + medium}
Mencioná los rubros y tipos de solución más frecuentes si podés inferirlos.
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
