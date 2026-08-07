"""Envía (o simula) WhatsApp a leads Mendoza ready vía Twilio.

Uso:
  # Dry-run (default): no llama a Twilio
  .venv\\Scripts\\python -m scripts.send_mendoza_whatsapp --limit 5

  # Live (requiere .env TWILIO_* y TWILIO_SEND_ENABLED=true)
  .venv\\Scripts\\python -m scripts.send_mendoza_whatsapp --live --limit 1
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
    parser = argparse.ArgumentParser(description="Enviar campaña WhatsApp Mendoza")
    parser.add_argument("--source", choices=("csv", "crm"), default="csv")
    parser.add_argument("--csv", type=str, default="", help="CSV ready")
    parser.add_argument("--limit", type=int, default=0, help="0 = todos")
    parser.add_argument("--live", action="store_true", help="Envío real (no dry-run)")
    parser.add_argument(
        "--mark-dry-crm",
        action="store_true",
        help="En dry-run también marcar CRM contacted (solo pruebas)",
    )
    args = parser.parse_args()

    from app.services.campaign_send import run_send_campaign

    result = await run_send_campaign(
        source=args.source,
        csv_path=args.csv or None,
        dry_run=not args.live,
        limit=args.limit or None,
        update_crm_on_dry_run=args.mark_dry_crm,
    )
    print(result.summary, flush=True)
    for item in result.items[:20]:
        flag = "OK" if item.ok else "FAIL"
        extra = item.sid or item.error or item.status or ""
        print(f"  [{flag}] {item.place_name} -> {item.to} {extra}", flush=True)
    if len(result.items) > 20:
        print(f"  … y {len(result.items) - 20} más", flush=True)
    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
