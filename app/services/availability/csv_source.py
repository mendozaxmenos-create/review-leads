"""Planilla CSV local = fuente real de disponibilidad (mismo contrato que Sheets/PMS)."""

from __future__ import annotations

import csv
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.services.availability import Cabin, CabinQuote, SourceInfo


def _parse_day(raw: str) -> date | None:
    text = (raw or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _overlaps(a_in: date, a_out: date, b_in: date, b_out: date) -> bool:
    # [check_in, check_out) half-open
    return a_in < b_out and b_in < a_out


class CsvAvailabilitySource:
    """Lee cabins + blocked_dates + prereservas bloqueantes desde un directorio."""

    def __init__(self, root: Path, *, deposit_pct: int = 30) -> None:
        self.root = Path(root)
        self.deposit_pct = max(1, min(100, int(deposit_pct)))
        self.cabins_path = self.root / "cabins.csv"
        self.blocked_path = self.root / "blocked_dates.csv"
        self.prereservas_path = self.root / "prereservas.csv"

    def info(self) -> SourceInfo:
        ok = self.cabins_path.exists() and self.blocked_path.exists()
        return SourceInfo(
            kind="csv",
            label="Planilla CSV (local)",
            detail=f"Leyendo {self.root.as_posix()}",
            connected=ok,
        )

    def list_cabins(self) -> list[Cabin]:
        if not self.cabins_path.exists():
            return []
        out: list[Cabin] = []
        with self.cabins_path.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                if (row.get("active") or "yes").strip().lower() in ("no", "false", "0"):
                    continue
                out.append(
                    Cabin(
                        id=(row.get("id") or "").strip(),
                        name=(row.get("name") or "").strip(),
                        capacity=int(float(row.get("capacity") or 2)),
                        price_night=int(float(row.get("price_night") or 0)),
                        type=(row.get("type") or "").strip(),
                        quality=(row.get("quality") or "").strip(),
                        amenities=(row.get("amenities") or "").strip(),
                        note=(row.get("note") or "").strip(),
                        active=True,
                    )
                )
        return [c for c in out if c.id and c.name]

    def _blocked_ranges(self) -> list[tuple[str, date, date]]:
        ranges: list[tuple[str, date, date]] = []
        if self.blocked_path.exists():
            with self.blocked_path.open(encoding="utf-8-sig", newline="") as fh:
                for row in csv.DictReader(fh):
                    cid = (row.get("cabin_id") or "").strip()
                    cin = _parse_day(row.get("check_in") or "")
                    cout = _parse_day(row.get("check_out") or "")
                    if cid and cin and cout and cin < cout:
                        ranges.append((cid, cin, cout))
        if self.prereservas_path.exists():
            with self.prereservas_path.open(encoding="utf-8-sig", newline="") as fh:
                for row in csv.DictReader(fh):
                    status = (row.get("status") or "").strip().upper()
                    if status in ("EXPIRED", "CANCELLED", "REJECTED", "PAYMENT_REJECTED"):
                        continue
                    cid = (row.get("cabin_id") or "").strip()
                    cin = _parse_day(row.get("check_in") or "")
                    cout = _parse_day(row.get("check_out") or "")
                    if cid and cin and cout and cin < cout:
                        ranges.append((cid, cin, cout))
        return ranges

    def find_available(
        self,
        *,
        check_in: date,
        check_out: date,
        guests: int,
    ) -> list[CabinQuote]:
        if check_out <= check_in:
            return []
        nights = (check_out - check_in).days
        blocked = self._blocked_ranges()
        quotes: list[CabinQuote] = []
        for cabin in self.list_cabins():
            if cabin.capacity < guests:
                continue
            busy = any(
                cid == cabin.id and _overlaps(check_in, check_out, b_in, b_out)
                for cid, b_in, b_out in blocked
            )
            if busy:
                continue
            total = cabin.price_night * nights
            deposit = int(round(total * self.deposit_pct / 100))
            quotes.append(
                CabinQuote(
                    cabin=cabin,
                    nights=nights,
                    total=total,
                    deposit_pct=self.deposit_pct,
                    deposit_amount=deposit,
                    available=True,
                )
            )
        return quotes

    def create_prereserva(self, row: dict[str, Any]) -> str:
        """Append or update by id (PRE_RESERVED → CONFIRMED no duplica filas)."""
        self.root.mkdir(parents=True, exist_ok=True)
        rid = (row.get("id") or "").strip() or f"PR-{uuid.uuid4().hex[:8].upper()}"
        fields = [
            "id",
            "cabin_id",
            "check_in",
            "check_out",
            "guest_name",
            "guests",
            "status",
            "total_amount",
            "deposit_amount",
            "created_at",
        ]
        payload = {
            "id": rid,
            "cabin_id": str(row.get("cabin_id") or ""),
            "check_in": str(row.get("check_in") or ""),
            "check_out": str(row.get("check_out") or ""),
            "guest_name": str(row.get("guest_name") or ""),
            "guests": str(row.get("guests") or ""),
            "status": str(row.get("status") or "PRE_RESERVED"),
            "total_amount": str(row.get("total_amount") or ""),
            "deposit_amount": str(row.get("deposit_amount") or ""),
            "created_at": str(
                row.get("created_at")
                or datetime.now(timezone.utc).isoformat(timespec="seconds")
            ),
        }
        existing: list[dict[str, str]] = []
        if self.prereservas_path.exists():
            with self.prereservas_path.open(encoding="utf-8-sig", newline="") as fh:
                existing = [{k: (v or "") for k, v in r.items()} for r in csv.DictReader(fh)]
        updated = False
        for i, prev in enumerate(existing):
            if (prev.get("id") or "").strip() == rid:
                merged = {**prev, **payload}
                if prev.get("created_at") and not row.get("created_at"):
                    merged["created_at"] = prev["created_at"]
                existing[i] = {f: merged.get(f, "") for f in fields}
                updated = True
                break
        if not updated:
            existing.append(payload)
        with self.prereservas_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            for item in existing:
                writer.writerow({f: item.get(f, "") for f in fields})
        return rid


def ensure_sample_planilla(root: Path) -> None:
    """Crea planilla demo si no existe (cabins + blocked)."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    cabins = root / "cabins.csv"
    blocked = root / "blocked_dates.csv"
    preres = root / "prereservas.csv"
    if not cabins.exists():
        with cabins.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(
                fh,
                fieldnames=[
                    "id",
                    "name",
                    "capacity",
                    "price_night",
                    "type",
                    "quality",
                    "amenities",
                    "note",
                    "active",
                ],
            )
            w.writeheader()
            for row in (
                {
                    "id": "calma",
                    "name": "Cabaña Calma",
                    "capacity": "2",
                    "price_night": "85000",
                    "type": "pareja",
                    "quality": "estándar",
                    "amenities": "Wifi, cocina, estacionamiento",
                    "note": "Ideal 2 personas",
                    "active": "yes",
                },
                {
                    "id": "hornero",
                    "name": "Cabaña Hornero",
                    "capacity": "4",
                    "price_night": "120000",
                    "type": "familiar",
                    "quality": "superior",
                    "amenities": "Wifi, cocineta, parrilla, estacionamiento",
                    "note": "Hasta 4",
                    "active": "yes",
                },
                {
                    "id": "quincho",
                    "name": "Cabaña del Quincho",
                    "capacity": "6",
                    "price_night": "165000",
                    "type": "familiar grande",
                    "quality": "premium",
                    "amenities": "Wifi, cocina completa, quincho, cochera",
                    "note": "Grupos",
                    "active": "yes",
                },
                {
                    "id": "esencia",
                    "name": "Cabaña Esencia",
                    "capacity": "4",
                    "price_night": "140000",
                    "type": "familiar",
                    "quality": "premium",
                    "amenities": "Wifi, hidromasaje, vista",
                    "note": "La más pedida",
                    "active": "yes",
                },
            ):
                w.writerow(row)
    if not blocked.exists():
        # Seed con fechas absolutas relativas a hoy (demo: algo ocupado, algo libre)
        today = date.today()
        with blocked.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["cabin_id", "check_in", "check_out", "note"])
            w.writeheader()
            w.writerow(
                {
                    "cabin_id": "hornero",
                    "check_in": today.isoformat(),
                    "check_out": (today + timedelta(days=3)).isoformat(),
                    "note": "ocupado demo",
                }
            )
            w.writerow(
                {
                    "cabin_id": "calma",
                    "check_in": (today + timedelta(days=7)).isoformat(),
                    "check_out": (today + timedelta(days=10)).isoformat(),
                    "note": "ocupado demo",
                }
            )
    if not preres.exists():
        with preres.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(
                fh,
                fieldnames=[
                    "id",
                    "cabin_id",
                    "check_in",
                    "check_out",
                    "guest_name",
                    "guests",
                    "status",
                    "total_amount",
                    "deposit_amount",
                    "created_at",
                ],
            )
            w.writeheader()
