"""Envía lotes live de la campaña Mendoza hasta alcanzar un tope o vaciar pendientes."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.mendoza_campaign import (  # noqa: E402
    campaign_dashboard_stats,
    run_mendoza_wa_campaign,
)


async def send_until(*, target_sent: int | None, batch_size: int, remaining_all: bool) -> int:
    total_ok = 0
    while True:
        stats = campaign_dashboard_stats()
        sent = int(stats["sent_live_unique"])
        pending = int(stats["pending_to_send"])
        print(f"estado: sent={sent} pending={pending}", flush=True)

        if pending <= 0:
            print("no hay pendientes", flush=True)
            break

        if not remaining_all and target_sent is not None and sent >= target_sent:
            print(f"alcanzado target_sent={target_sent}", flush=True)
            break

        limit = batch_size
        if not remaining_all and target_sent is not None:
            limit = min(batch_size, max(0, target_sent - sent))
            if limit <= 0:
                break

        result = await run_mendoza_wa_campaign(
            dry_run=False,
            limit=limit,
            skip_already_sent=True,
            mark_contacted=True,
        )
        data = result.model_dump()
        ok = int(data.get("sent_ok") or 0)
        failed = int(data.get("failed") or 0)
        total_ok += ok
        print(
            f"lote: total={data.get('total')} ok={ok} failed={failed} | {data.get('summary')}",
            flush=True,
        )
        if ok == 0:
            print("lote sin envíos OK — freno", flush=True)
            break

    final = campaign_dashboard_stats()
    print(
        f"fin: sent={final['sent_live_unique']} pending={final['pending_to_send']} ok_esta_corrida={total_ok}",
        flush=True,
    )
    return total_ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-sent", type=int, default=None, help="Parar al llegar a N enviados live únicos")
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument(
        "--remaining-all",
        action="store_true",
        help="Enviar todos los pendientes (ignora target-sent)",
    )
    args = parser.parse_args()

    if not args.remaining_all and args.target_sent is None:
        parser.error("Indicá --target-sent N o --remaining-all")

    asyncio.run(
        send_until(
            target_sent=args.target_sent,
            batch_size=args.batch_size,
            remaining_all=args.remaining_all,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
