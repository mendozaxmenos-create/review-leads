"""Lista Priority operativos (humanos que respondieron) para cierre manual.

Uso:
  python -m scripts.list_priority_leads
  python -m scripts.list_priority_leads --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.store import get_store
from app.routers.demo import public_demo_share_url
from app.services.campaign_ops import (
    OPS_STAGE_LABELS,
    demo_url_for_place,
    is_priority_thread,
    resolve_ops_stage,
)
from app.services.mendoza_campaign import CAMPAIGN_ID, CAMPAIGN_TAG
from app.services.reply_classify import classify_inbound_thread


def _collect(limit: int = 200) -> list[dict]:
    store = get_store()
    store.init()
    demo_base = public_demo_share_url() or "https://review-leads.onrender.com/demo"
    rows: list[dict] = []
    seen: set[str] = set()
    for status in ("responded", "follow_up"):
        for r in store.list_campaign_leads_by_status(CAMPAIGN_TAG, status, limit=limit):
            lead = r["lead"]
            place_id = r["place_id"]
            if place_id in seen:
                continue
            msgs = store.list_campaign_messages(CAMPAIGN_ID, place_id=place_id, limit=40)
            inbound = [m for m in reversed(msgs) if m.get("direction") == "inbound"]
            thread = classify_inbound_thread([m.get("body") for m in inbound])
            if not is_priority_thread(thread.get("thread_kind")):
                continue
            ops = resolve_ops_stage(r["status"], lead)
            if ops in {"closed", "lost"}:
                continue
            seen.add(place_id)
            phone = lead.get("phone") or ""
            digits = "".join(ch for ch in phone if ch.isdigit())
            last = (inbound[-1].get("body") if inbound else "") or ""
            name = lead.get("place_name") or ""
            rows.append(
                {
                    "place_id": place_id,
                    "place_name": name,
                    "zone": lead.get("zone"),
                    "base": lead.get("base") or "Mendoza",
                    "phone": phone,
                    "ops_stage": ops,
                    "ops_stage_label": OPS_STAGE_LABELS[ops],
                    "status": r["status"],
                    "thread_kind": thread.get("thread_kind"),
                    "thread_label": thread.get("thread_label"),
                    "last_reply": last,
                    "wa_me": f"https://wa.me/{digits}" if digits else None,
                    "demo_url": demo_url_for_place(name, demo_base),
                    "updated_at": r.get("updated_at"),
                }
            )
    rows.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="List Priority leads for manual close")
    parser.add_argument("--json", action="store_true", help="Print JSON")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()
    rows = _collect(limit=args.limit)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    print(f"Priority activos: {len(rows)}\n")
    for i, r in enumerate(rows, 1):
        print(f"{i}. {r['place_name']} · {r['zone'] or '—'} · {r['base']}")
        print(f"   tel: {r['phone'] or '—'}  |  etapa: {r['ops_stage_label']}")
        print(f"   last: {(r['last_reply'] or '—').replace(chr(10), ' ')[:200]}")
        if r.get("wa_me"):
            print(f"   WA: {r['wa_me']}")
        print(f"   demo: {r['demo_url']}")
        print()
    print("Checklist cierre: contactar → demo ?nombre= → marcar etapa en /campaign → closed/lost")
    print("Twilio: CAMPAIGN_SEND_PAUSED=true hasta piloto ≤20 o primer cliente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
