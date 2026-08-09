"""Marca en CRM como discarded los leads quarantineados por online_booking."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def mark_quarantine_booking_discarded(quarantine_csv: Path) -> dict:
    from app.db.store import get_store

    if not quarantine_csv.exists():
        return {"ok": False, "error": f"missing {quarantine_csv}", "updated": 0}

    store = get_store()
    store.init()
    updated = 0
    skipped = 0
    with quarantine_csv.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            reason = (row.get("etl_reason") or "").strip()
            if not reason.startswith("online_booking"):
                continue
            place_id = (row.get("place_id") or "").strip()
            if not place_id:
                skipped += 1
                continue
            meta = store.get_saved_leads_by_places([place_id]).get(place_id)
            if not meta:
                skipped += 1
                continue
            # No pisar follow_up / responded humanos activos
            if meta.get("status") in ("follow_up", "responded"):
                skipped += 1
                continue
            note = (meta.get("notes") or "").strip()
            discard_note = f"Descartado ETL: {reason}"
            store.update_saved_lead(
                meta["saved_lead_id"],
                status="discarded",
                notes=(note + (" | " if note else "") + discard_note),
            )
            updated += 1
    return {"ok": True, "updated": updated, "skipped": skipped, "csv": str(quarantine_csv)}


def main() -> int:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--quarantine", required=True, help="CSV quarantine del ETL")
    args = p.parse_args()
    result = mark_quarantine_booking_discarded(Path(args.quarantine))
    print(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
