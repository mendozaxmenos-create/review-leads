"""Corre Ola 1: sweep → ETL (booking) → sync CRM por cada base.

Uso:
  .venv\\Scripts\\python -m scripts.run_cabanas_ola1
  .venv\\Scripts\\python -m scripts.run_cabanas_ola1 --bases "San Luis,Salta"
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


async def pipeline_one(base: str, *, max_places: int, fetch_booking: bool) -> dict:
    from scripts.cabanas_sweep import main as sweep_main  # type: ignore

    # Run sweep as subprocess for clean argv / isolation
    py = sys.executable
    sweep = subprocess.run(
        [
            py,
            "-m",
            "scripts.cabanas_sweep",
            "--base",
            base,
            "--mode",
            "directory",
            "--max-places",
            str(max_places),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    print(sweep.stdout)
    if sweep.returncode != 0:
        print(sweep.stderr, file=sys.stderr)
        return {"base": base, "ok": False, "stage": "sweep", "stderr": sweep.stderr[-2000:]}

    # Find newest sweep CSV for this base
    from scripts.etl_cabanas_base import _default_input_for_base, _slug_base, run_etl
    from app.services.mendoza_campaign import sync_etl_clean_to_crm
    from scripts.mark_booking_discards import mark_quarantine_booking_discarded
    from pathlib import Path as P

    export = ROOT / "data" / "exports"
    slug = _slug_base(base).lower()
    sweeps = sorted(export.glob(f"{slug}-cabanas-2*.csv"), reverse=True)
    # also try without lower
    if not sweeps:
        sweeps = sorted(export.glob(f"*{slug.split('-')[0]}*cabanas-2*.csv"), reverse=True)
    src = sweeps[0] if sweeps else _default_input_for_base(base)
    if not src or not P(src).exists():
        return {"base": base, "ok": False, "stage": "find_csv"}

    report = run_etl(base_name=base, src=P(src), fetch_booking=fetch_booking)
    sync = sync_etl_clean_to_crm(csv_path=P(report["outputs"]["clean"]), base_name=base)
    discarded = mark_quarantine_booking_discarded(P(report["outputs"]["quarantine"]))
    return {
        "base": base,
        "ok": True,
        "sweep_csv": str(src),
        "clean": report["clean_rows"],
        "quarantine": report["quarantine_rows"],
        "online_booking": report["online_booking_rejected"],
        "sync": sync,
        "discarded": discarded,
    }


async def main() -> int:
    from app.data.ar_locations import CABANAS_OLA1_ORDER

    parser = argparse.ArgumentParser()
    parser.add_argument("--bases", default="", help="Lista coma-separada (default: Ola 1 completa)")
    parser.add_argument("--max-places", type=int, default=35)
    parser.add_argument("--no-fetch-booking", action="store_true")
    args = parser.parse_args()

    bases = [b.strip() for b in args.bases.split(",") if b.strip()] or list(CABANAS_OLA1_ORDER)
    results = []
    for base in bases:
        print("=" * 60, flush=True)
        print(f"OLA1 → {base}", flush=True)
        r = await pipeline_one(
            base,
            max_places=args.max_places,
            fetch_booking=not args.no_fetch_booking,
        )
        print(r, flush=True)
        results.append(r)

    print("=" * 60, flush=True)
    print("RESUMEN OLA 1", flush=True)
    for r in results:
        if r.get("ok"):
            print(
                f"  {r['base']}: clean={r['clean']} quar={r['quarantine']} "
                f"booking={r['online_booking']} sync_ins={r['sync'].get('inserted')} "
                f"upd={r['sync'].get('updated')}",
                flush=True,
            )
        else:
            print(f"  {r['base']}: FAIL {r}", flush=True)
    return 0 if all(r.get("ok") for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
