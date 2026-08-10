"""Seguimiento ops de Priority (post-reply humano) — sin blast Twilio."""

from __future__ import annotations

from typing import Any

OPS_STAGES: tuple[str, ...] = ("pending", "contacted", "demo", "closed", "lost")

OPS_STAGE_LABELS: dict[str, str] = {
    "pending": "Pendiente",
    "contacted": "Contactado",
    "demo": "Demo enviada",
    "closed": "Cerrado",
    "lost": "Perdido",
}

# ops_stage → pipeline status en saved_leads
_OPS_TO_STATUS: dict[str, str] = {
    "pending": "responded",
    "contacted": "follow_up",
    "demo": "follow_up",
    "closed": "closed",
    "lost": "discarded",
}


def normalize_ops_stage(value: str | None) -> str | None:
    raw = (value or "").strip().lower()
    return raw if raw in OPS_STAGES else None


def resolve_ops_stage(status: str | None, lead: dict[str, Any] | None) -> str:
    """Etapa ops explícita en lead_json, o inferida del status del pipeline."""
    lead = lead or {}
    explicit = normalize_ops_stage(lead.get("ops_stage"))
    if explicit:
        return explicit
    st = (status or "").strip().lower()
    if st == "discarded":
        return "lost"
    if st == "closed":
        return "closed"
    if st == "follow_up":
        return "contacted"
    return "pending"


def pipeline_status_for_ops(ops_stage: str) -> str:
    stage = normalize_ops_stage(ops_stage)
    if not stage:
        raise ValueError(f"ops_stage inválido: {ops_stage!r}")
    return _OPS_TO_STATUS[stage]


def is_priority_thread(thread_kind: str | None) -> bool:
    kind = (thread_kind or "").strip()
    return kind in {"human_only", "human_after_auto", "empty_only"}


def demo_url_for_place(place_name: str | None, base_demo_url: str) -> str:
    base = (base_demo_url or "").rstrip("/")
    name = (place_name or "").strip()
    if not name:
        return base
    from urllib.parse import quote

    return f"{base}?nombre={quote(name)}"
