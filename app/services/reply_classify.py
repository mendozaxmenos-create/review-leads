"""Clasifica respuestas WhatsApp inbound: auto-reply de bot vs humano."""

from __future__ import annotations

import re
from typing import Any

OPT_OUT = {
    "STOP",
    "UNSUBSCRIBE",
    "CANCEL",
    "CANCELAR",
    "BAJA",
    "NO",
    "NO GRACIAS",
    "NO, GRACIAS",
}

# Frases típicas de bots de reservas / bienvenida automática
_AUTO_PHRASES = (
    "gracias por comunicarte",
    "gracias por contactar",
    "gracias por contactarnos",
    "gracias por escribir",
    "gracias por escribirnos",
    "gracias por tu mensaje",
    "gracias por su consulta",
    "gracias por comunicarse",
    "gracias por su interés",
    "apreciamos su interés",
    "agradezco tu mensaje",
    "agradece tu mensaje",
    "qué alegría tu mensaje",
    "que alegria tu mensaje",
    "bienvenido a",
    "bienvenidos a",
    "te damos la bienvenida",
    "como podemos ayudarte",
    "¿cómo podemos ayudarte",
    "en qué podemos ayudarte",
    "en breve nos pondremos",
    "a la brevedad",
    "te responderé lo antes",
    "te contestaremos a la brevedad",
    "en este momento no podemos responder",
    "para realizar una reserva",
    "para reservar por favor",
    "indícanos en qué fechas",
    "indicanos en que fechas",
    "dejanos tu nombre y consulta",
    "dejanos tu consulta",
    "asistente virtual",
    "este contacto es exclusivo",
    "para brindarte la información",
    "si desea conocer disponibilidad",
    "nuestra administración es de",
    "esta conversación utiliza una integración",
    "sin disponibilidad",
    "hola somos",
    "contamos con",
    "para pasarte disponibilidad",
    "en un momento respondemos",
    "en un momento te respondemos",
    "en breve respondemos",
    "se a comunicado con",
    "se ha comunicado con",
    "usted se a comunicado",
    "te has comunicado con",
    "recepción de",
    "recepcion de",
)

_AUTO_LABEL = {
    "auto_reply": "Auto-reply (bot)",
    "human": "Humano",
    "stop": "Opt-out / STOP",
    "empty": "Sin texto (botón/reacción)",
}

_THREAD_LABEL = {
    "human_only": "Respuesta humana",
    "human_after_auto": "Humano retomó después del auto-reply",
    "auto_only": "Solo auto-reply — un humano puede retomar después",
    "stop": "Pidió no contactar",
    "empty_only": "Interacción sin texto — conviene mirar el chat",
    "none": "Sin respuesta",
}


def normalize_opt_out(body: str) -> str:
    return re.sub(r"\s+", " ", (body or "").strip()).upper().rstrip(".!")


def is_opt_out(body: str) -> bool:
    return normalize_opt_out(body) in OPT_OUT


def classify_inbound_body(body: str | None) -> str:
    """
    Clasifica un mensaje inbound suelto.
    Returns: stop | empty | auto_reply | human
    """
    text = (body or "").strip()
    if not text:
        return "empty"
    if is_opt_out(text):
        return "stop"

    lower = text.lower()
    phrase_hits = sum(1 for p in _AUTO_PHRASES if p in lower)
    longish = len(text) > 70
    asks_booking = any(
        k in lower
        for k in (
            "reserva",
            "disponibilidad",
            "fechas",
            "personas",
            "aloj",
            "cabañ",
            "hosped",
        )
    )

    # Bienvenida / menú de bot: frases típicas + largo o pedido de datos de reserva
    if phrase_hits >= 1 and (longish or asks_booking):
        return "auto_reply"
    if phrase_hits >= 2:
        return "auto_reply"
    if longish and asks_booking and phrase_hits >= 1:
        return "auto_reply"

    # Menú / ficha comercial automática (aunque no diga "gracias por…")
    if longish and asks_booking and (
        "wifi" in lower
        or "desayuno" in lower
        or "tarifa" in lower
        or "complejo" in lower
        or text.count("*") >= 2
    ):
        return "auto_reply"

    return "human"


def classify_inbound_thread(inbound_bodies_oldest_first: list[str | None]) -> dict[str, Any]:
    """
    Resume el hilo inbound del lead.
    No descarta el caso por un auto-reply: deja explícito que un humano puede retomar.
    """
    kinds = [classify_inbound_body(b) for b in inbound_bodies_oldest_first]
    if not kinds:
        thread = "none"
    elif "stop" in kinds and not any(k == "human" for k in kinds):
        thread = "stop"
    elif any(k == "human" for k in kinds) and any(k == "auto_reply" for k in kinds):
        # Humano en cualquier momento + hubo bot → "retomó" (aunque el orden varíe)
        first_auto = next((i for i, k in enumerate(kinds) if k == "auto_reply"), None)
        first_human = next((i for i, k in enumerate(kinds) if k == "human"), None)
        if first_auto is not None and first_human is not None and first_human > first_auto:
            thread = "human_after_auto"
        elif first_human is not None and first_auto is not None and first_human < first_auto:
            # Humano primero y después bot (raro pero pasa) — igual hay humano
            thread = "human_after_auto"
        else:
            thread = "human_after_auto"
    elif any(k == "human" for k in kinds):
        thread = "human_only"
    elif any(k == "auto_reply" for k in kinds):
        thread = "auto_only"
    elif any(k == "stop" for k in kinds):
        thread = "stop"
    else:
        thread = "empty_only"

    last_body = ""
    last_kind = "empty"
    if inbound_bodies_oldest_first:
        last_body = (inbound_bodies_oldest_first[-1] or "").strip()
        last_kind = kinds[-1]

    priority = {
        "human_after_auto": 0,
        "human_only": 1,
        "empty_only": 2,
        "auto_only": 3,
        "stop": 4,
        "none": 5,
    }.get(thread, 9)

    return {
        "thread_kind": thread,
        "thread_label": _THREAD_LABEL[thread],
        "last_kind": last_kind,
        "last_kind_label": _AUTO_LABEL.get(last_kind, last_kind),
        "last_body": last_body,
        "inbound_count": len(kinds),
        "kinds": kinds,
        "priority": priority,
        "needs_you": thread in ("human_only", "human_after_auto", "empty_only"),
        "waiting_human_possible": thread == "auto_only",
    }


def note_for_inbound(kind: str, body: str, *, thread_kind: str | None = None) -> str:
    """Texto corto para notes del CRM."""
    snippet = (body or "").strip().replace("\n", " ")[:100]
    if kind == "stop":
        return f"Opt-out WhatsApp: {snippet or 'STOP'}"
    if kind == "auto_reply":
        base = f"Auto-reply (bot de reservas): {snippet[:80]}" if snippet else "Auto-reply (bot de reservas)"
        return base + " — un humano puede retomar después"
    if kind == "empty":
        return "Respondió sin texto (botón/reacción) — mirar chat"
    if thread_kind == "human_after_auto":
        return f"Humano retomó después del auto-reply: {snippet}" if snippet else "Humano retomó después del auto-reply"
    return f"Respuesta humana: {snippet}" if snippet else "Respuesta humana"
