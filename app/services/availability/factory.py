"""Factory de fuentes de disponibilidad."""

from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.services.availability import AvailabilitySource, SourceInfo
from app.services.availability.csv_source import CsvAvailabilitySource, ensure_sample_planilla

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CSV_DIR = ROOT / "data" / "demo_availability"


def _csv_source() -> CsvAvailabilitySource:
    root = Path(settings.availability_csv_dir or DEFAULT_CSV_DIR)
    if not root.is_absolute():
        root = ROOT / root
    ensure_sample_planilla(root)
    return CsvAvailabilitySource(root, deposit_pct=settings.availability_deposit_pct)


def _sheets_source() -> AvailabilitySource:
    from app.services.availability.sheets_source import (
        SheetsAvailabilitySource,
        SheetsConfigError,
        load_service_account_info,
    )

    legacy = (settings.availability_sheets_spreadsheet_id or "").strip()
    calendar_id = (settings.availability_sheets_calendar_spreadsheet_id or "").strip() or legacy
    reservations_id = (
        (settings.availability_sheets_reservations_spreadsheet_id or "").strip() or legacy
    )
    try:
        sa = load_service_account_info(
            json_inline=settings.google_service_account_json,
            json_file=settings.google_service_account_file,
            client_email=settings.google_service_account_email,
            private_key=settings.google_private_key,
        )
        return SheetsAvailabilitySource(
            calendar_spreadsheet_id=calendar_id,
            reservations_spreadsheet_id=reservations_id,
            cabins_range=settings.availability_sheets_cabins_range,
            blocked_range=settings.availability_sheets_blocked_range,
            reservations_range=settings.availability_sheets_reservations_range,
            service_account_info=sa,
            deposit_pct=settings.availability_deposit_pct,
        )
    except SheetsConfigError:
        raise
    except Exception as exc:  # noqa: BLE001 — surface clear factory error
        raise SheetsConfigError(f"No se pudo inicializar Google Sheets: {exc}") from exc


def get_availability_source() -> AvailabilitySource:
    kind = (settings.availability_source or "csv").strip().lower()
    if kind in ("sheets", "google_sheets", "gsheets", "google"):
        return _sheets_source()
    if kind in ("csv", "planilla", "file", "memory", ""):
        return _csv_source()
    # unknown → CSV demo (siempre hay fuente local sin credenciales)
    return _csv_source()


def availability_source_info() -> dict:
    try:
        src = get_availability_source()
        info: SourceInfo = src.info()
        return {
            "kind": info.kind,
            "label": info.label,
            "detail": info.detail,
            "connected": info.connected,
            "cabins": len(src.list_cabins()),
        }
    except Exception as exc:  # noqa: BLE001 — demo panel must not 500
        kind = (settings.availability_source or "csv").strip().lower() or "csv"
        return {
            "kind": kind,
            "label": "Fuente no conectada",
            "detail": str(exc),
            "connected": False,
            "cabins": 0,
            "error": str(exc),
        }
