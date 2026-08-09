"""Snapshot CRM pending + Twilio readiness for Monday sends."""
from __future__ import annotations

from app.services.mendoza_campaign import (
    CAMPAIGN_TAG,
    _blockers,
    campaign_dashboard_stats,
    twilio_billing_snapshot,
)
from app.db.store import get_store


def main() -> None:
    store = get_store()
    store.init()
    print("=== BASES ===")
    for b in store.list_campaign_bases(CAMPAIGN_TAG):
        print(
            f"{b['base']:28} leads={b['leads']:4} sent={b['sent']:4} pend={b['pending']:4}"
        )
    print("=== BLOCKERS ===")
    blockers = _blockers()
    if not blockers:
        print("(none)")
    for x in blockers:
        print("-", x)
    d = campaign_dashboard_stats()
    print(
        "universe",
        d["universe"],
        "pending",
        d["pending_to_send"],
        "sent",
        d["sent_live_unique"],
        "human",
        d["responded_human"],
    )
    bill = twilio_billing_snapshot()
    print("balance", bill["twilio_balance"])
    print("usage", bill["twilio_usage"])


if __name__ == "__main__":
    main()
