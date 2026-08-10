"""Fuente de disponibilidad para el bot (planilla CSV / Sheets)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol


@dataclass
class Cabin:
    id: str
    name: str
    capacity: int
    price_night: int
    type: str = ""
    quality: str = ""
    amenities: str = ""
    note: str = ""
    active: bool = True


@dataclass
class CabinQuote:
    cabin: Cabin
    nights: int
    total: int
    deposit_pct: int
    deposit_amount: int
    available: bool = True


@dataclass
class SourceInfo:
    kind: str  # csv | sheets | memory
    label: str
    detail: str
    connected: bool = True


class AvailabilitySource(Protocol):
    def info(self) -> SourceInfo: ...

    def list_cabins(self) -> list[Cabin]: ...

    def find_available(
        self,
        *,
        check_in: date,
        check_out: date,
        guests: int,
    ) -> list[CabinQuote]: ...

    def create_prereserva(self, row: dict[str, Any]) -> str:
        """Append pre-reserva; returns id."""
        ...
