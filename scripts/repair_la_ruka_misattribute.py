"""Reparación one-shot: mensaje de La Ruka mal atribuido a Segundo Calvario."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.store import get_store
from app.services.mendoza_campaign import CAMPAIGN_ID
from app.services.reply_classify import classify_inbound_thread


def main() -> int:
    store = get_store()
    store.init()
    ruka_pid = "ChIJ1cnneXex0pURZr79jQ8SfUU"
    calv_pid = "ChIJ6USF8385G5QRzutKjBD7ytM"
    human_note = (
        "Respuesta humana: Hola Sofía, contame estos $19.000 al mes es el total a pagar?"
    )

    with store._connect() as conn:
        n = conn.execute(
            """
            UPDATE campaign_messages
            SET place_id = ?
            WHERE campaign = ? AND direction = 'inbound' AND place_id = ?
            """,
            (ruka_pid, CAMPAIGN_ID, calv_pid),
        ).rowcount
        conn.commit()
    print(f"messages reassigned: {n}")

    with store._connect() as conn:
        row = conn.execute(
            "SELECT id, notes FROM saved_leads WHERE place_id = ?",
            (ruka_pid,),
        ).fetchone()
    note = (row["notes"] or "").strip()
    if human_note not in note:
        note = note + (" | " if note else "") + human_note
    store.update_saved_lead(row["id"], status="responded", notes=note)
    print("La Ruka → responded + nota humana")

    with store._connect() as conn:
        crow = conn.execute(
            "SELECT id FROM saved_leads WHERE place_id = ?",
            (calv_pid,),
        ).fetchone()
    store.update_saved_lead(crow["id"], status="new", notes="")
    print("Segundo Calvario → new (nota limpia)")

    found = store.find_lead_by_phone_digits("5493546521195")
    name = (found.get("lead") or {}).get("place_name") if found else None
    print(f"find_lead_by_phone → {name} / {found.get('place_id') if found else None}")

    empty_trap = store.find_lead_by_phone_digits("5499999999999")
    print(f"empty-phone trap match → {empty_trap is not None}")

    msgs = store.list_campaign_messages(CAMPAIGN_ID, place_id=ruka_pid, limit=20)
    inbounds = [m["body"] for m in reversed(msgs) if m.get("direction") == "inbound"]
    print("ruka inbounds:", len(inbounds), classify_inbound_thread(inbounds))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
