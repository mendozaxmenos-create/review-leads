import json
from urllib.parse import quote

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
        themes_line = ", ".join(lead.themes) if lead.themes else "Sin temas específicos"

        prompt = f"""Generá un mensaje de primer contacto para vender: {project_name}
Descripción del servicio: {description}

Canal: {channel}
Negocio: {lead.place_name}
Dirección: {lead.address or "N/A"}
Teléfono en Google: {lead.phone or "no disponible"}
Email en Google: {lead.email or "no disponible"}
Web: {lead.website or "no disponible"}

Temas de queja detectados ({lead.reviews_count} reseñas): {themes_line}

Reseñas relevantes:
"{lead.review_text}"

Por qué es lead: {lead.reason}

Reglas:
- Español rioplatense profesional pero cercano
- Mencioná los dolores detectados (temas) sin citar reseñas textualmente de forma invasiva
- Propuesta de valor clara en 2-3 oraciones
- CTA concreto (llamada, demo, reunión de 15 min)
- Máximo 600 caracteres si es whatsapp
- No inventes datos de contacto ni links

JSON:
{{
  "subject": "asunto si es email, o null",
  "body": "mensaje listo para enviar",
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
        body = data.get("body", "")
        subject = data.get("subject")
        tips = data.get("tips")

        whatsapp_link = None
        email_link = None

        if channel == "whatsapp":
            whatsapp_link = self._whatsapp_link(lead.phone, body)
            if not whatsapp_link:
                tips = (tips or "") + " Google no tiene teléfono para este negocio."
        elif channel == "email":
            email_link = self._email_link(lead.email, subject, body)
            if not email_link:
                tips = (tips or "") + " Google no publica email para este negocio en la API."

        return OutreachMessage(
            channel=channel,
            subject=subject,
            body=body,
            whatsapp_link=whatsapp_link,
            email_link=email_link,
            contact_phone=lead.phone,
            contact_email=lead.email,
            tips=tips.strip() if tips else None,
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
        themes_line = ", ".join(lead.themes) if lead.themes else "Sin temas específicos"

        system = f"""Sos un bot de ventas que contacta a {lead.place_name} para ofrecer {project_name}.
Descripción: {description}

Contexto del lead:
- Temas de queja: {themes_line}
- Reseñas: "{lead.review_text}"
- Por qué es lead: {lead.reason}
- Relevancia: {lead.lead_fit}
- Teléfono Google: {lead.phone or "N/A"}

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
    def _whatsapp_link(phone: str | None, message: str) -> str | None:
        if not phone:
            return None
        digits = "".join(c for c in phone if c.isdigit())
        if len(digits) < 8:
            return None
        return f"https://wa.me/{digits}?text={quote(message[:500])}"

    @staticmethod
    def _email_link(email: str | None, subject: str | None, body: str) -> str | None:
        if not email or "@" not in email:
            return None
        params = [f"body={quote(body[:2000])}"]
        if subject:
            params.insert(0, f"subject={quote(subject)}")
        return f"mailto:{email}?{'&'.join(params)}"
