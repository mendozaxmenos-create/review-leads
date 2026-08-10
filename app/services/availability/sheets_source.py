"""Google Sheets AvailabilitySource — config-driven, any owner.

Dual-planilla pattern (read calendar / write prereservas only):
- Calendar spreadsheet: cabins + blocked dates (bot is reader; never writes calendar).
- Reservations spreadsheet: append/update prereservas (bot needs editor).

Tabular headers match the CSV planilla (`cabins`, `blocked_dates`, `prereservas`).
Sheet names / ranges and spreadsheet IDs come from env — no client hardcoding.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from app.services.availability import Cabin, CabinQuote, SourceInfo
from app.services.availability.csv_source import _overlaps, _parse_day

SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)

PRERESERVA_FIELDS = [
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


class SheetsConfigError(RuntimeError):
    """Raised when sheets mode is selected but credentials / IDs are missing."""


def _cell(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        if key in row and row[key] is not None:
            return str(row[key]).strip()
        lower = key.lower()
        for rk, rv in row.items():
            if rk.lower() == lower and rv is not None:
                return str(rv).strip()
    return ""


def _rows_to_dicts(matrix: list[list[Any]]) -> list[dict[str, str]]:
    if not matrix:
        return []
    headers = [str(h or "").strip() for h in matrix[0]]
    out: list[dict[str, str]] = []
    for raw in matrix[1:]:
        if not any(str(c or "").strip() for c in raw):
            continue
        row: dict[str, str] = {}
        for i, header in enumerate(headers):
            if not header:
                continue
            row[header] = str(raw[i]).strip() if i < len(raw) and raw[i] is not None else ""
        out.append(row)
    return out


def load_service_account_info(
    *,
    json_inline: str = "",
    json_file: str = "",
    client_email: str = "",
    private_key: str = "",
) -> dict[str, Any]:
    """Resolve service-account credentials from env knobs (all optional until sheets mode)."""
    inline = (json_inline or "").strip()
    if inline:
        try:
            data = json.loads(inline)
        except json.JSONDecodeError as exc:
            raise SheetsConfigError(
                "GOOGLE_SERVICE_ACCOUNT_JSON no es JSON válido."
            ) from exc
        if not isinstance(data, dict) or not data.get("client_email") or not data.get("private_key"):
            raise SheetsConfigError(
                "GOOGLE_SERVICE_ACCOUNT_JSON debe incluir client_email y private_key."
            )
        return data

    path = (json_file or "").strip()
    if path:
        p = Path(path)
        if not p.is_file():
            raise SheetsConfigError(f"No existe el archivo de service account: {path}")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SheetsConfigError(f"JSON inválido en {path}") from exc
        if not isinstance(data, dict) or not data.get("client_email") or not data.get("private_key"):
            raise SheetsConfigError(
                f"{path} debe incluir client_email y private_key."
            )
        return data

    email = (client_email or "").strip()
    key = (private_key or "").strip().replace("\\n", "\n")
    if email and key:
        return {
            "type": "service_account",
            "client_email": email,
            "private_key": key,
            "token_uri": "https://oauth2.googleapis.com/token",
        }

    raise SheetsConfigError(
        "Modo sheets requiere credenciales Google: seteá "
        "GOOGLE_SERVICE_ACCOUNT_JSON, o GOOGLE_SERVICE_ACCOUNT_FILE, "
        "o GOOGLE_SERVICE_ACCOUNT_EMAIL + GOOGLE_PRIVATE_KEY."
    )


def build_sheets_service(info: dict[str, Any]):
    """Lazy-import google libs so CSV demo works without them installed."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise SheetsConfigError(
            "Faltan dependencias Google Sheets. Instalá: "
            "pip install google-auth google-api-python-client"
        ) from exc

    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


class SheetsAvailabilitySource:
    """Lee calendario (cabins + blocked) y escribe solo en hoja de pre-reservas."""

    def __init__(
        self,
        *,
        calendar_spreadsheet_id: str,
        reservations_spreadsheet_id: str,
        cabins_range: str,
        blocked_range: str,
        reservations_range: str,
        service_account_info: dict[str, Any],
        deposit_pct: int = 30,
        sheets_service: Any | None = None,
    ) -> None:
        if not calendar_spreadsheet_id.strip():
            raise SheetsConfigError(
                "Falta AVAILABILITY_SHEETS_CALENDAR_SPREADSHEET_ID "
                "(o AVAILABILITY_SHEETS_SPREADSHEET_ID)."
            )
        if not reservations_spreadsheet_id.strip():
            raise SheetsConfigError(
                "Falta AVAILABILITY_SHEETS_RESERVATIONS_SPREADSHEET_ID "
                "(o AVAILABILITY_SHEETS_SPREADSHEET_ID)."
            )
        self.calendar_id = calendar_spreadsheet_id.strip()
        self.reservations_id = reservations_spreadsheet_id.strip()
        self.cabins_range = cabins_range.strip() or "Cabins!A:Z"
        self.blocked_range = blocked_range.strip() or "BlockedDates!A:Z"
        self.reservations_range = reservations_range.strip() or "Prereservas!A:Z"
        self.deposit_pct = max(1, min(100, int(deposit_pct)))
        self._info = service_account_info
        self._service = sheets_service
        self._sa_email = str(service_account_info.get("client_email") or "")

    def _api(self):
        if self._service is None:
            self._service = build_sheets_service(self._info)
        return self._service

    def _get_values(self, spreadsheet_id: str, range_a1: str) -> list[list[Any]]:
        result = (
            self._api()
            .spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=range_a1)
            .execute()
        )
        return result.get("values") or []

    def _update_values(self, spreadsheet_id: str, range_a1: str, values: list[list[Any]]) -> None:
        (
            self._api()
            .spreadsheets()
            .values()
            .update(
                spreadsheetId=spreadsheet_id,
                range=range_a1,
                valueInputOption="USER_ENTERED",
                body={"values": values},
            )
            .execute()
        )

    def info(self) -> SourceInfo:
        detail = (
            f"Calendario={self.calendar_id[:8]}… · "
            f"Pre-reservas={self.reservations_id[:8]}… · "
            f"solo lectura en calendario"
        )
        if self._sa_email:
            detail += f" · SA={self._sa_email}"
        return SourceInfo(
            kind="sheets",
            label="Google Sheets (planilla del dueño)",
            detail=detail,
            connected=True,
        )

    def list_cabins(self) -> list[Cabin]:
        rows = _rows_to_dicts(self._get_values(self.calendar_id, self.cabins_range))
        out: list[Cabin] = []
        for row in rows:
            active = _cell(row, "active").lower()
            if active in ("no", "false", "0"):
                continue
            cid = _cell(row, "id", "cabin_id")
            name = _cell(row, "name", "cabin_name", "nombre")
            if not cid or not name:
                continue
            capacity_raw = _cell(row, "capacity", "capacidad") or "2"
            price_raw = _cell(row, "price_night", "base_price", "precio", "tarifa") or "0"
            out.append(
                Cabin(
                    id=cid,
                    name=name,
                    capacity=int(float(capacity_raw)),
                    price_night=int(float(price_raw)),
                    type=_cell(row, "type", "tipo"),
                    quality=_cell(row, "quality"),
                    amenities=_cell(row, "amenities", "amenidades"),
                    note=_cell(row, "note", "notes", "nota"),
                    active=True,
                )
            )
        return out

    def _blocked_ranges(self) -> list[tuple[str, date, date]]:
        ranges: list[tuple[str, date, date]] = []
        for row in _rows_to_dicts(self._get_values(self.calendar_id, self.blocked_range)):
            cid = _cell(row, "cabin_id", "id")
            cin = _parse_day(_cell(row, "check_in", "checkin", "desde", "fecha_in"))
            cout = _parse_day(_cell(row, "check_out", "checkout", "hasta", "fecha_out"))
            if cid and cin and cout and cin < cout:
                ranges.append((cid, cin, cout))
        for row in _rows_to_dicts(
            self._get_values(self.reservations_id, self.reservations_range)
        ):
            status = _cell(row, "status", "estado").upper()
            if status in ("EXPIRED", "CANCELLED", "REJECTED", "PAYMENT_REJECTED"):
                continue
            cabin = _cell(row, "cabin_id")
            cin = _parse_day(_cell(row, "check_in", "checkin", "desde"))
            cout = _parse_day(_cell(row, "check_out", "checkout", "hasta"))
            if cabin and cin and cout and cin < cout:
                ranges.append((cabin, cin, cout))
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
        """Append or update by id on the reservations sheet only (never calendar)."""
        rid = (row.get("id") or "").strip() or f"PR-{uuid.uuid4().hex[:8].upper()}"
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
        matrix = self._get_values(self.reservations_id, self.reservations_range)
        if not matrix:
            values = [PRERESERVA_FIELDS, [payload[f] for f in PRERESERVA_FIELDS]]
            self._update_values(self.reservations_id, self.reservations_range, values)
            return rid

        headers = [str(h or "").strip() for h in matrix[0]]
        if not any(headers):
            headers = list(PRERESERVA_FIELDS)
            matrix = [headers]

        # Ensure required columns exist
        for field in PRERESERVA_FIELDS:
            if field not in headers:
                headers.append(field)

        id_col = headers.index("id") if "id" in headers else 0
        updated = False
        new_rows: list[list[str]] = [headers]
        for raw in matrix[1:]:
            cells = [str(raw[i]).strip() if i < len(raw) and raw[i] is not None else "" for i in range(len(headers))]
            while len(cells) < len(headers):
                cells.append("")
            existing_id = cells[id_col] if id_col < len(cells) else ""
            if existing_id == rid:
                for i, field in enumerate(headers):
                    if field in payload:
                        if field == "created_at" and cells[i] and not row.get("created_at"):
                            continue
                        cells[i] = payload[field]
                updated = True
            new_rows.append(cells)

        if not updated:
            new_rows.append([payload.get(h, "") for h in headers])

        sheet_name = self.reservations_range.split("!")[0]
        self._update_values(self.reservations_id, f"{sheet_name}!A1", new_rows)
        return rid
