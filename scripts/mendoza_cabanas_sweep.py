"""CLI: barrido de cabañas en zonas turísticas de Mendoza.

Uso:
  .venv\\Scripts\\python -m scripts.mendoza_cabanas_sweep
  .venv\\Scripts\\python -m scripts.mendoza_cabanas_sweep --mode leads --no-cache
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

# Permitir importar app desde la raíz del repo
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


async def main() -> int:
    parser = argparse.ArgumentParser(description="Campaña Mendoza · cabañas")
    parser.add_argument(
        "--mode",
        choices=("directory", "leads"),
        default="directory",
        help="directory = contactos rápidos; leads = clasificar reseñas con IA",
    )
    parser.add_argument("--max-places", type=int, default=40, help="Máx. lugares por zona")
    parser.add_argument("--no-cache", action="store_true", help="Ignorar caché")
    parser.add_argument(
        "--zones",
        type=str,
        default="",
        help="IDs de zona separados por coma (vacío = todas)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="",
        help="Ruta CSV de salida (default: data/exports/...)",
    )
    args = parser.parse_args()

    from app.db.store import get_store
    from app.models.schemas import MendozaCabanasCampaignRequest
    from app.routers.campaigns import run_mendoza_cabanas

    get_store().init()

    zone_ids = [z.strip() for z in args.zones.split(",") if z.strip()] or None
    body = MendozaCabanasCampaignRequest(
        mode=args.mode,
        max_places_per_zone=args.max_places,
        use_cache=not args.no_cache,
        zone_ids=zone_ids,
    )

    print(
        f"Iniciando campaña Mendoza cabañas (mode={args.mode}, zonas={zone_ids or 'todas'})…",
        flush=True,
    )
    result = await run_mendoza_cabanas(body)

    export_dir = ROOT / "data" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = Path(args.out) if args.out else export_dir / f"mendoza-cabanas-{stamp}.csv"

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
            row = lead.model_dump()
            writer.writerow(row)

    summary_path = out_path.with_suffix(".json")
    summary_path.write_text(
        json.dumps(
            {
                "summary": result.summary,
                "zones": [z.model_dump() for z in result.zones],
                "leads_unique": result.leads_unique,
                "with_phone": result.with_phone,
                "search_history_id": result.search_history_id,
                "csv": str(out_path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(result.summary)
    for z in result.zones:
        status = "OK" if not z.error else f"ERR: {z.error}"
        print(f"  · {z.zone_label}: {z.leads_count} leads ({z.with_phone} tel) — {status}")
    print(f"CSV: {out_path}")
    print(f"Resumen: {summary_path}")
    print(f"CRM history_id: {result.search_history_id}")
    return 0 if result.zones_ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
