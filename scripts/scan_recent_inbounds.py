"""Scan recent inbound messages for empty-phone / wrong attribution."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.store import get_store
from app.services.mendoza_campaign import CAMPAIGN_ID


def main() -> int:
    store = get_store()
    store.init()
    with store._connect() as conn:
        rows = conn.execute(
            """
            SELECT m.place_id, m.body, m.created_at, m.phone AS msg_phone,
                   s.status, s.lead_json
            FROM campaign_messages m
            LEFT JOIN saved_leads s ON s.place_id = m.place_id
            WHERE m.campaign = ? AND m.direction = 'inbound'
              AND datetime(m.created_at) >= datetime('now', '-3 days')
            ORDER BY m.created_at DESC
            LIMIT 40
            """,
            (CAMPAIGN_ID,),
        ).fetchall()
    print(f"recent inbounds: {len(rows)}")
    for r in rows:
        lead = json.loads(r["lead_json"] or "{}") if r["lead_json"] else {}
        ph = (lead.get("phone") or "").strip()
        campaign = lead.get("campaign") or ""
        base = lead.get("base") or lead.get("zone") or "-"
        name = (lead.get("place_name") or "?")[:42]
        if not ph:
            flag = "NO_PHONE"
        elif not campaign:
            flag = "no_campaign"
        else:
            flag = "ok"
        body = (r["body"] or "")[:55].replace("\n", " ")
        print(
            f"{r['created_at']} | {str(base)[:12]:12} | {str(r['status'] or '-'):10} | "
            f"{flag:12} | {name} | {body}"
        )

    with store._connect() as conn:
        row = conn.execute(
            "SELECT status, notes, lead_json FROM saved_leads WHERE place_id = ?",
            ("ChIJ1cnneXex0pURZr79jQ8SfUU",),
        ).fetchone()
    lead = json.loads(row["lead_json"]) if row else {}
    print("---")
    print(
        "La Ruka:",
        {
            "place_name": lead.get("place_name"),
            "base": lead.get("base"),
            "status": row["status"] if row else None,
            "notes": (row["notes"] or "")[:120] if row else None,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
