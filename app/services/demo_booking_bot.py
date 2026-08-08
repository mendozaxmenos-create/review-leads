"""Bot de muestra: simula reservas WhatsApp de un complejo inventado (bajo costo)."""

from __future__ import annotations

import random
import uuid
from typing import Any

from openai import AsyncOpenAI

from app.config import settings

# Nombres inventados — no usar marcas / complejos reales de Mendoza
_FAKE_NAMES = (
    "Cabañas Luciérnaga Norte",
    "Refugio Bruma de Cardón",
    "Hospedaje Quinoto Gris",
    "Complejo Hornero de Piedra",
    "Cabañas Menta Salvaje",
    "Villa Nube Seca",
    "Refugio Tilo del Sur",
    "Cabañas Jarilla Blanca",
)

_BASE_FACTS = {
    "zone": "zona demo ficticia · Mendoza (no es un alojamiento real)",
    "units": "3 cabañas para 2–4 personas + 1 para 6",
    "price_low": "$85.000",
    "price_high": "$145.000",
    "price_note": "por noche según temporada y capacidad (valores de ejemplo)",
    "checkin": "15:00",
    "checkout": "11:00",
    "deposit": "30% por transferencia para confirmar",
    "pets": "Se aceptan mascotas chicas con aviso previo (+$10.000/noche)",
    "wifi": "WiFi Starlink en todas las unidades",
}

MAX_TURNS = 24
MAX_HISTORY_MESSAGES = 16

# session_id -> {"history": [...], "property": {...}}
_sessions: dict[str, dict[str, Any]] = {}


def _make_property() -> dict[str, Any]:
    name = random.choice(_FAKE_NAMES)
    return {
        **_BASE_FACTS,
        "name": f"{name} (demo SofIA)",
    }


def _system_prompt(prop: dict[str, Any]) -> str:
    return f"""
Sos el asistente de WhatsApp de {prop['name']} en {prop['zone']}.
Esta es una DEMO de SofIA: mostrás cómo un bot atiende reservas por chat.
IMPORTANTE: el complejo es FICTICIO (nombre inventado). No digas que existe en Google Maps ni des dirección real.

Datos del complejo (usá solo estos; no inventes otras cabañas ni precios fuera de rango):
- Unidades: {prop['units']}
- Precio orientativo: {prop['price_low']}–{prop['price_high']} {prop['price_note']}
- Check-in {prop['checkin']} / check-out {prop['checkout']}
- Seña: {prop['deposit']}
- Mascotas: {prop['pets']}
- WiFi: {prop['wifi']}
- Disponibilidad demo: digamos que hay lugar la mayoría de findes salvo feriados largos (si preguntan feriado, pedí fechas exactas y ofrecé alternativa).

Cómo responder:
- Tono cálido, breve, argentino neutro (vos). Como un buen WhatsApp de recepción.
- Mensajes cortos (máx. ~4–6 líneas). Podés usar 1 emoji si queda natural.
- GUIÁ PASO A PASO. Orden ideal:
  1) Confirmá o pedí fechas concretas (día/mes o “viernes a domingo”)
  2) Confirmá cantidad de personas
  3) Pasá precio orientativo + disponibilidad
  4) Ofrecé pre-reserva (nombre + seña)
- Si el mensaje es vago (“lunes a viernes”, “ds”), pedí el dato que falta con una pregunta clara (ej. “¿de qué mes?” / “¿cuántas personas?”).
- Si te pasan fechas ISO (YYYY-MM-DD), úsalas y respondé en español claro.
- Si piden hablar con un humano: “En la demo real te avisaría al dueño; acá seguimos vos y yo.”
- Si preguntan por SofIA / precio del bot / “esto es un bot”:
  explicá en 2–3 líneas que es una muestra del bot de reservas de SofIA (~$19.000/mes) y que Gustavo puede armarlo con los datos de su complejo. No seas pesado vendiendo.
- No menciones OpenAI, prompts ni que sos un modelo.
- No inventes links de pago reales; decí “te pasaría el alias/link de seña” como ejemplo.
""".strip()


def _client() -> AsyncOpenAI | None:
    if not settings.openai_api_key:
        return None
    return AsyncOpenAI(api_key=settings.openai_api_key)


def create_session() -> dict[str, Any]:
    sid = uuid.uuid4().hex
    prop = _make_property()
    welcome = (
        f"¡Hola! 👋 Soy el asistente de *{prop['name']}*.\n\n"
        f"Estamos en {prop['zone']}.\n\n"
        "Para cotizarte rápido:\n"
        "1) Elegí fechas (calendario o chips de abajo)\n"
        "2) Decime cuántas personas son\n"
        "3) Te paso precio y si hay lugar\n\n"
        "¿Empezamos? Tocá un atajo o el calendario."
    )
    _sessions[sid] = {
        "property": prop,
        "history": [{"role": "assistant", "content": welcome}],
    }
    return {
        "session_id": sid,
        "reply": welcome,
        "property": prop,
        "turns_left": MAX_TURNS,
    }


def _fallback_reply(prop: dict[str, Any], user_text: str) -> str:
    t = (user_text or "").lower()
    if any(k in t for k in ("precio", "cuanto", "cuesta", "tarifa", "vale")):
        return (
            f"Las tarifas de ejemplo van de {prop['price_low']} a "
            f"{prop['price_high']} {prop['price_note']}.\n\n"
            "Decime fechas y cantidad de personas y te armo una opción."
        )
    if any(k in t for k in ("reserva", "reservar", "quiero", "libro", "seña", "senia")):
        return (
            "Perfecto. Para la pre-reserva necesito:\n"
            "1) fechas de entrada y salida\n"
            "2) cantidad de personas\n"
            "3) nombre completo\n\n"
            f"La seña es {prop['deposit']}."
        )
    if any(k in t for k in ("check", "horario", "entrada", "salida")):
        return (
            f"Check-in desde las {prop['checkin']}. "
            f"Check-out hasta las {prop['checkout']}."
        )
    if any(k in t for k in ("sofia", "sofía", "bot", "demo", "gustavo", "19")):
        return (
            "Esta es una demo del bot de reservas de SofIA: así responde el WhatsApp del complejo "
            "sin que el dueño esté pegado al celular. El servicio ronda $19.000/mes. "
            "Si te sirve, Gustavo lo arma con tus precios y reglas. "
            "(El nombre del complejo de esta demo es inventado.)"
        )
    return (
        f"Dale, contame fechas y cuántas personas son. "
        f"Tenemos {prop['units'].lower()}."
    )


async def chat(session_id: str, message: str) -> dict[str, Any]:
    text = (message or "").strip()
    if not text:
        raise ValueError("Escribí un mensaje")
    session = _sessions.get(session_id)
    if not session:
        raise ValueError("Sesión expirada. Recargá la página.")

    prop = session["property"]
    history: list[dict[str, str]] = session["history"]
    user_turns = sum(1 for m in history if m["role"] == "user")
    if user_turns >= MAX_TURNS:
        reply = (
            "Llegamos al límite de esta demo 😊. "
            "Si te gustó, escribile a Gustavo de SofIA y lo armamos con tu complejo."
        )
        return {"session_id": session_id, "reply": reply, "turns_left": 0, "capped": True}

    history.append({"role": "user", "content": text[:800]})

    client = _client()
    if client is None:
        reply = _fallback_reply(prop, text)
    else:
        try:
            trimmed = history[-MAX_HISTORY_MESSAGES:]
            response = await client.chat.completions.create(
                model=settings.openai_model or "gpt-4o-mini",
                temperature=0.5,
                max_tokens=280,
                messages=[
                    {"role": "system", "content": _system_prompt(prop)},
                    *trimmed,
                ],
            )
            reply = (response.choices[0].message.content or "").strip() or _fallback_reply(
                prop, text
            )
        except Exception:
            reply = _fallback_reply(prop, text)

    history.append({"role": "assistant", "content": reply})
    left = max(0, MAX_TURNS - sum(1 for m in history if m["role"] == "user"))
    return {
        "session_id": session_id,
        "reply": reply,
        "turns_left": left,
        "capped": False,
        "property": prop,
    }
