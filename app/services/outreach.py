import json

from openai import AsyncOpenAI

from app.config import settings
from app.data.services import get_profile
from app.models.schemas import ChatMessage, ConversationResponse, LeadInput, OutreachMessage


class OutreachService:
    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY no está configurada")
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    def _project_context(self, project_id: str | None, project_description: str | None) -> tuple[str, str]:
        if project_id:
            profile = get_profile(project_id)
            if profile:
                return profile.name, profile.description
        return "Servicio custom", project_description or ""

    async def generate_message(
        self,
        *,
        lead: LeadInput,
        project_id: str | None,
        project_description: str | None,
        channel: str = "whatsapp",
    ) -> OutreachMessage:
        project_name, description = self._project_context(project_id, project_description)

        prompt = f"""Generá un mensaje de primer contacto para vender: {project_name}
Descripción del servicio: {description}

Canal: {channel}
Negocio: {lead.place_name}
Dirección: {lead.address or "N/A"}
Teléfono: {lead.phone or "no disponible"}
Web: {lead.website or "no disponible"}

Reseña que motivó el lead ({lead.lead_fit}):
"{lead.review_text}"

Por qué es lead: {lead.reason}

Reglas:
- Español rioplatense profesional pero cercano
- Mencioná el dolor detectado en la reseña sin citarla textualmente de forma invasiva
- Propuesta de valor clara en 2-3 oraciones
- CTA concreto (llamada, demo, reunión de 15 min)
- Máximo 600 caracteres si es whatsapp
- No inventes datos de contacto

JSON:
{{
  "subject": "asunto si es email, o null",
  "body": "mensaje listo para enviar",
  "whatsapp_link": "https://wa.me/... solo si hay teléfono normalizable, sino null",
  "tips": "consejo breve para el vendedor"
}}
"""

        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=0.5,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "Sos copywriter de ventas B2B. Respondé solo JSON válido.",
                },
                {"role": "user", "content": prompt},
            ],
        )

        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
        wa_link = data.get("whatsapp_link")
        if not wa_link and lead.phone:
            wa_link = self._whatsapp_link(lead.phone, data.get("body", ""))

        return OutreachMessage(
            channel=channel,
            subject=data.get("subject"),
            body=data.get("body", ""),
            whatsapp_link=wa_link,
            tips=data.get("tips"),
        )

    async def converse(
        self,
        *,
        lead: LeadInput,
        project_id: str | None,
        project_description: str | None,
        messages: list[ChatMessage],
    ) -> ConversationResponse:
        project_name, description = self._project_context(project_id, project_description)

        system = f"""Sos un bot de ventas que contacta a {lead.place_name} para ofrecer {project_name}.
Descripción: {description}

Contexto del lead:
- Reseña: "{lead.review_text}"
- Por qué es lead: {lead.reason}
- Relevancia: {lead.lead_fit}

Objetivo: responder, presentar valor, manejar objeciones y avanzar al cierre (reunión/demo/presupuesto).
Etapas: intro → discovery → offer → objection → close

Respondé JSON:
{{
  "reply": "tu mensaje al cliente",
  "stage": "intro|discovery|offer|objection|close",
  "next_action": "qué debería hacer el vendedor después",
  "close_probability": 0-100
}}
Escribí como si chatearas por WhatsApp, español rioplatense, conciso."""

        chat_messages = [{"role": "system", "content": system}]
        for msg in messages:
            chat_messages.append({"role": msg.role, "content": msg.content})

        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=0.6,
            response_format={"type": "json_object"},
            messages=chat_messages,
        )

        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)

        return ConversationResponse(
            reply=data.get("reply", ""),
            stage=data.get("stage", "intro"),
            next_action=data.get("next_action", ""),
            close_probability=int(data.get("close_probability", 20)),
        )

    @staticmethod
    def _whatsapp_link(phone: str, message: str) -> str | None:
        digits = "".join(c for c in phone if c.isdigit())
        if len(digits) < 8:
            return None
        from urllib.parse import quote

        return f"https://wa.me/{digits}?text={quote(message[:500])}"
