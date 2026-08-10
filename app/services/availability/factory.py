"""Factory de fuentes de disponibilidad."""

from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.services.availability import AvailabilitySource, SourceInfo
from app.services.availability.csv_source import CsvAvailabilitySource, ensure_sample_planilla

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CSV_DIR = ROOT / "data" / "demo_availability"


def get_availability_source() -> AvailabilitySource:
    kind = (settings.availability_source or "csv").strip().lower()
    if kind in ("csv", "planilla", "file"):
        root = Path(settings.availability_csv_dir or DEFAULT_CSV_DIR)
        if not root.is_absolute():
            root = ROOT / root
        ensure_sample_planilla(root)
        return CsvAvailabilitySource(root, deposit_pct=settings.availability_deposit_pct)
    # memory / unknown → CSV demo igual (siempre hay fuente real de planilla)
    root = DEFAULT_CSV_DIR
    ensure_sample_planilla(root)
    return CsvAvailabilitySource(root, deposit_pct=settings.availability_deposit_pct)


def availability_source_info() -> dict:
    src = get_availability_source()
    info: SourceInfo = src.info()
    return {
        "kind": info.kind,
        "label": info.label,
        "detail": info.detail,
        "connected": info.connected,
        "cabins": len(src.list_cabins()),
    }
