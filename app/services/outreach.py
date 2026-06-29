import json
from urllib.parse import quote

from openai import AsyncOpenAI

from app.config import settings, outreach_sender_signature
from app.data.outreach_guidelines import CONVERSATION_RULES, FIRST_CONTACT_RULES, GOOGLE_REVIEWS_SOURCE_RULES
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
        sender = outreach_sender_signature()

        prompt = f"""Generá un mensaje de primer contacto para vender: {project_name}
Descripción del servicio: {description}

Quién envía el mensaje (VOS / el vendedor): {sender}
Negocio al que le escribís (el cliente / destinatario): {lead.place_name}
Canal: {channel}
Dirección del negocio: {lead.address or "N/A"}
Teléfono del negocio en Google: {lead.phone or "no disponible"}
Email del negocio en Google: {lead.email or "no disponible"}
Web del negocio: {lead.website or "no disponible"}

Temas de queja en reseñas de Google ({lead.reviews_count} reseñas analizadas): {themes_line}

Fragmentos de reseñas de clientes en Google:
"{lead.review_text}"

Por qué es lead (según reseñas de Google): {lead.reason}

Reglas:
- Español rioplatense profesional pero cercano
- El mensaje lo escribe {sender} contactando A {lead.place_name}
- NUNCA digas "soy de {lead.place_name}" ni te identifiques como el negocio contactado
- Empezá presentándote, ej: "Hola, soy {sender}."
{GOOGLE_REVIEWS_SOURCE_RULES}
{FIRST_CONTACT_RULES}
- Máximo 700 caracteres si es whatsapp
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
                    "content": (
                        "Sos copywriter de ventas B2B por WhatsApp. "
                        "Los dolores mencionados deben atribuirse a reseñas de clientes en Google. "
                        "El primer contacto NUNCA propone reunión: primero interés y opciones. "
                        "Respondé solo JSON válido."
                    ),
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
        sender = outreach_sender_signature()

        system = f"""Sos {sender}, un vendedor que contacta por WhatsApp al negocio "{lead.place_name}" para ofrecer {project_name}.
Descripción del servicio: {description}

IMPORTANTE: Vos sos {sender}. El cliente es {lead.place_name}. Nunca te identifiques como {lead.place_name}.

Contexto del lead (reseñas públicas de clientes en Google Maps):
- Temas de queja en Google: {themes_line}
- Reseñas: "{lead.review_text}"
- Por qué es lead: {lead.reason}
- Relevancia: {lead.lead_fit}
- Teléfono Google: {lead.phone or "N/A"}

Objetivo: generar interés, presentar opciones concretas, responder dudas y avanzar sin presionar.
{GOOGLE_REVIEWS_SOURCE_RULES}
{CONVERSATION_RULES}
Etapas: intro → interest → options → objection → close (reunión solo en close y si hubo interés previo)

Respondé JSON:
{{
  "reply": "tu mensaje al cliente",
  "stage": "intro|interest|options|objection|close",
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
