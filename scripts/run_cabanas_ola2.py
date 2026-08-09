"""Corre Ola 2: sweep → ETL (booking) → sync CRM por cada base.

No envía WhatsApp. Deja pendientes listos para el dashboard.

Uso:
  .venv\\Scripts\\python -m scripts.run_cabanas_ola2
  .venv\\Scripts\\python -m scripts.run_cabanas_ola2 --bases "Catamarca,La Rioja"
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


async def main() -> int:
    from app.data.ar_locations import CABANAS_OLA2_ORDER
    from scripts.run_cabanas_ola1 import pipeline_one

    parser = argparse.ArgumentParser()
    parser.add_argument("--bases", default="", help="Lista coma-separada (default: Ola 2 completa)")
    parser.add_argument("--max-places", type=int, default=35)
    parser.add_argument("--no-fetch-booking", action="store_true")
    args = parser.parse_args()

    bases = [b.strip() for b in args.bases.split(",") if b.strip()] or list(CABANAS_OLA2_ORDER)
    results = []
    for base in bases:
        print("=" * 60, flush=True)
        print(f"OLA2 → {base}", flush=True)
        r = await pipeline_one(
            base,
            max_places=args.max_places,
            fetch_booking=not args.no_fetch_booking,
        )
        print(r, flush=True)
        results.append(r)

    print("=" * 60, flush=True)
    print("RESUMEN OLA 2", flush=True)
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
