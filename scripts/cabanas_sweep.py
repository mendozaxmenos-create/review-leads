"""CLI genérico: barrido de cabañas por base (Ola 1 / Mendoza / Córdoba).

Uso:
  .venv\\Scripts\\python -m scripts.cabanas_sweep --base "San Luis"
  .venv\\Scripts\\python -m scripts.cabanas_sweep --base "Río Negro" --max-places 35
  .venv\\Scripts\\python -m scripts.cabanas_sweep --list-bases
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


async def main() -> int:
    from app.data.ar_locations import (
        CABANAS_BASES,
        cabanas_base_center,
        list_cabanas_base_names,
        list_cabanas_zones_for_base,
    )
    from app.db.store import get_store
    from app.models.schemas import MendozaCabanasCampaignRequest
    from app.routers.campaigns import run_cabanas_zones

    parser = argparse.ArgumentParser(description="Barrido cabañas multi-base")
    parser.add_argument("--list-bases", action="store_true")
    parser.add_argument("--base", default="", help="Nombre de base CRM")
    parser.add_argument("--mode", choices=("directory", "leads"), default="directory")
    parser.add_argument("--max-places", type=int, default=35)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--zones", type=str, default="", help="IDs zona coma-separados")
    parser.add_argument("--out", type=str, default="")
    args = parser.parse_args()

    if args.list_bases:
        for name in list_cabanas_base_names():
            print(f"{name}: {len(CABANAS_BASES[name])} zonas")
        return 0

    base = (args.base or "").strip()
    if not base:
        print("Pasá --base o --list-bases", file=sys.stderr)
        return 1

    zones = list_cabanas_zones_for_base(base)
    zone_ids = [z.strip() for z in args.zones.split(",") if z.strip()] or None
    get_store().init()

    slug = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in base)[:40].lower()
    campaign = f"{slug}-cabanas"
    center = cabanas_base_center(base)

    body = MendozaCabanasCampaignRequest(
        mode=args.mode,
        max_places_per_zone=args.max_places,
        use_cache=not args.no_cache,
        zone_ids=zone_ids,
    )
    print(
        f"Sweep base={base} mode={args.mode} zonas={zone_ids or 'todas'} max={args.max_places}",
        flush=True,
    )
    result = await run_cabanas_zones(
        zones=zones,
        req=body,
        campaign=campaign,
        region_label=base,
        default_center=center,
    )

    export_dir = ROOT / "data" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = Path(args.out) if args.out else export_dir / f"{slug}-cabanas-{stamp}.csv"

    fields = [
        "place_name",
        "address",
        "phone",
        "website",
        "google_maps_url",
        "rating",
        "business_type_label",
        "recommended_project_name",
        "lead_fit",
        "status",
        "reason",
        "place_id",
    ]
    with out_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for lead in result.leads:
            writer.writerow(lead.model_dump())

    summary_path = out_path.with_suffix(".json")
    summary_path.write_text(
        json.dumps(
            {
                "base": base,
                "summary": result.summary,
                "zones": [z.model_dump() for z in result.zones],
                "leads_unique": result.leads_unique,
                "with_phone": result.with_phone,
                "places_scanned": result.places_scanned,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(result.summary, flush=True)
    print(f"CSV: {out_path}", flush=True)
    print(f"JSON: {summary_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
