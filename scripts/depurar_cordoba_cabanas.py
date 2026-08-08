"""Depura el CSV de la campaña Córdoba · cabañas.

Uso:
  .venv\\Scripts\\python -m scripts.depurar_cordoba_cabanas
  .venv\\Scripts\\python -m scripts.depurar_cordoba_cabanas --csv data/exports/cordoba-cabanas-....csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _default_csv() -> Path:
    export_dir = ROOT / "data" / "exports"
    candidates = sorted(export_dir.glob("cordoba-cabanas-*.csv"), reverse=True)
    for path in candidates:
        name = path.name
        if any(x in name for x in ("ready", "discarded", "etl")):
            continue
        return path
    raise FileNotFoundError("No hay CSV cordoba-cabanas-*.csv en data/exports")


def main() -> int:
    parser = argparse.ArgumentParser(description="Depurar leads Córdoba cabañas")
    parser.add_argument("--csv", type=str, default="", help="CSV de entrada")
    parser.add_argument("--no-crm", action="store_true", help="No actualizar estados en CRM")
    parser.add_argument("--limit", type=int, default=0, help="Máx. filas a procesar (0 = todas)")
    args = parser.parse_args()

    from app.data.cabanas_filter import classify_cabana_lead
    from app.db.store import get_store

    csv_path = Path(args.csv) if args.csv else _default_csv()
    if not csv_path.exists():
        print(f"No existe: {csv_path}")
        return 1

    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    if args.limit > 0:
        rows = rows[: args.limit]

    ready: list[dict] = []
    discarded: list[dict] = []
    reasons = Counter()

    for row in rows:
        ok, reason = classify_cabana_lead(row)
        reasons[reason] += 1
        out = dict(row)
        out["depurar_reason"] = reason
        out["depurar_ready"] = "yes" if ok else "no"
        if ok:
            ready.append(out)
        else:
            discarded.append(out)

    export_dir = ROOT / "data" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    ready_path = export_dir / f"cordoba-cabanas-ready-{stamp}.csv"
    discarded_path = export_dir / f"cordoba-cabanas-discarded-{stamp}.csv"
    ready_stable = export_dir / "cordoba-cabanas-ready.csv"
    discarded_stable = export_dir / "cordoba-cabanas-discarded.csv"

    out_fields = fieldnames + [f for f in ("depurar_reason", "depurar_ready") if f not in fieldnames]

    def write_csv(path: Path, data: list[dict]) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=out_fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(data)

    write_csv(ready_path, ready)
    write_csv(discarded_path, discarded)
    write_csv(ready_stable, ready)
    write_csv(discarded_stable, discarded)

    crm_updated = 0
    if not args.no_crm:
        store = get_store()
        store.init()
        place_ids = [r.get("place_id", "") for r in rows if r.get("place_id")]
        meta = store.get_saved_leads_by_places(place_ids)
        for row in discarded:
            pid = row.get("place_id") or ""
            info = meta.get(pid)
            if not info:
                continue
            if info["status"] in ("contacted", "responded", "closed"):
                continue
            store.update_saved_lead(
                info["saved_lead_id"],
                status="discarded",
                notes=f"Depurado Córdoba: {row.get('depurar_reason')}",
            )
            crm_updated += 1

    print(f"Entrada: {csv_path}")
    print(f"Total: {len(rows)}")
    print(f"Ready: {len(ready)} ({sum(1 for r in ready if (r.get('phone') or '').strip())} con teléfono)")
    print(f"Discarded: {len(discarded)}")
    print("Motivos:")
    for reason, count in reasons.most_common():
        print(f"  · {reason}: {count}")
    print(f"CRM discarded actualizados: {crm_updated}")
    print(f"Ready CSV: {ready_stable}")
    print(f"Discarded CSV: {discarded_stable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
