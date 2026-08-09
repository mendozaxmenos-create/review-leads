import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.config import settings
from app.data.services import ServiceProfile

_store: "Store | None" = None


def get_store() -> "Store":
    global _store
    if _store is None:
        _store = Store(settings.database_path)
        _store.init()
    return _store


class Store:
    def __init__(self, db_path: str | Path) -> None:
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS search_cache (
                    cache_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS custom_projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    lead_criteria TEXT NOT NULL,
                    suggested_business_types TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS search_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    project_id TEXT,
                    project_name TEXT,
                    business_type TEXT NOT NULL,
                    center_lat REAL NOT NULL,
                    center_lng REAL NOT NULL,
                    radius_km REAL NOT NULL,
                    places_scanned INTEGER NOT NULL,
                    leads_count INTEGER NOT NULL,
                    from_cache INTEGER NOT NULL DEFAULT 0,
                    request_json TEXT NOT NULL,
                    response_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS saved_leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    place_id TEXT NOT NULL UNIQUE,
                    search_history_id INTEGER,
                    status TEXT NOT NULL DEFAULT 'new',
                    notes TEXT,
                    lead_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (search_history_id) REFERENCES search_history(id)
                );
                CREATE INDEX IF NOT EXISTS idx_saved_leads_status ON saved_leads(status);
                CREATE INDEX IF NOT EXISTS idx_search_history_created ON search_history(created_at DESC);
                CREATE TABLE IF NOT EXISTS campaign_sends (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign TEXT NOT NULL,
                    place_id TEXT NOT NULL,
                    place_name TEXT,
                    phone TEXT,
                    zone TEXT,
                    dry_run INTEGER NOT NULL DEFAULT 1,
                    ok INTEGER NOT NULL DEFAULT 0,
                    twilio_sid TEXT,
                    twilio_status TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_campaign_sends_campaign ON campaign_sends(campaign, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_campaign_sends_place ON campaign_sends(campaign, place_id);
                CREATE TABLE IF NOT EXISTS campaign_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign TEXT NOT NULL,
                    place_id TEXT,
                    phone TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    body TEXT,
                    twilio_sid TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_campaign_messages_phone ON campaign_messages(phone, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_campaign_messages_place ON campaign_messages(campaign, place_id, created_at DESC);
                """
            )

    def get_search_cache(self, cache_key: str) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM search_cache WHERE cache_key = ? AND expires_at > ?",
                (cache_key, now),
            ).fetchone()
        if not row:
            return None
        return json.loads(row["payload"])

    def set_search_cache(self, cache_key: str, payload: dict[str, Any], ttl_hours: int) -> None:
        expires = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO search_cache (cache_key, payload, expires_at)
                VALUES (?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload = excluded.payload,
                    expires_at = excluded.expires_at
                """,
                (cache_key, json.dumps(payload, ensure_ascii=False), expires.isoformat()),
            )

    def list_custom_projects(self) -> list[ServiceProfile]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM custom_projects ORDER BY name COLLATE NOCASE"
            ).fetchall()
        return [self._row_to_profile(row) for row in rows]

    def get_custom_profile(self, project_id: str) -> ServiceProfile | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM custom_projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        return self._row_to_profile(row) if row else None

    def create_custom_project(
        self,
        *,
        name: str,
        description: str,
        lead_criteria: str,
        suggested_business_types: list[str],
    ) -> ServiceProfile:
        now = datetime.now(timezone.utc).isoformat()
        project_id = f"custom-{uuid.uuid4().hex[:10]}"
        types_json = json.dumps(suggested_business_types, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO custom_projects
                (id, name, description, lead_criteria, suggested_business_types, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (project_id, name, description, lead_criteria, types_json, now, now),
            )
        return ServiceProfile(
            id=project_id,
            name=name,
            description=description,
            lead_criteria=lead_criteria,
            suggested_business_types=suggested_business_types,
        )

    def update_custom_project(
        self,
        project_id: str,
        *,
        name: str,
        description: str,
        lead_criteria: str,
        suggested_business_types: list[str],
    ) -> ServiceProfile | None:
        now = datetime.now(timezone.utc).isoformat()
        types_json = json.dumps(suggested_business_types, ensure_ascii=False)
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE custom_projects
                SET name = ?, description = ?, lead_criteria = ?,
                    suggested_business_types = ?, updated_at = ?
                WHERE id = ?
                """,
                (name, description, lead_criteria, types_json, now, project_id),
            )
            if cur.rowcount == 0:
                return None
        return self.get_custom_profile(project_id)

    def delete_custom_project(self, project_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM custom_projects WHERE id = ?", (project_id,))
            return cur.rowcount > 0

    def save_search_history(
        self,
        *,
        request: dict[str, Any],
        response: dict[str, Any],
        from_cache: bool,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        center = request.get("center", {})
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO search_history (
                    created_at, project_id, project_name, business_type,
                    center_lat, center_lng, radius_km, places_scanned, leads_count,
                    from_cache, request_json, response_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    response.get("project_id"),
                    response.get("project_name"),
                    request.get("business_type") or "all",
                    center.get("lat"),
                    center.get("lng"),
                    request.get("radius_km"),
                    response.get("places_scanned", 0),
                    len(response.get("leads", [])),
                    1 if from_cache else 0,
                    json.dumps(request, ensure_ascii=False),
                    json.dumps(response, ensure_ascii=False),
                ),
            )
            return int(cur.lastrowid)

    def list_search_history(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, project_id, project_name, business_type,
                       center_lat, center_lng, radius_km, places_scanned, leads_count, from_cache
                FROM search_history
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_search_history(self, history_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM search_history WHERE id = ?",
                (history_id,),
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["request"] = json.loads(data.pop("request_json"))
        data["response"] = json.loads(data.pop("response_json"))
        return data

    def upsert_saved_lead(
        self,
        *,
        place_id: str,
        lead: dict[str, Any],
        search_history_id: int | None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        lead_json = json.dumps(lead, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO saved_leads (place_id, search_history_id, status, notes, lead_json, updated_at)
                VALUES (?, ?, 'new', NULL, ?, ?)
                ON CONFLICT(place_id) DO UPDATE SET
                    search_history_id = excluded.search_history_id,
                    lead_json = excluded.lead_json,
                    updated_at = excluded.updated_at
                """,
                (place_id, search_history_id, lead_json, now),
            )
            row = conn.execute(
                "SELECT id, place_id, status, notes FROM saved_leads WHERE place_id = ?",
                (place_id,),
            ).fetchone()
        result = dict(row)
        result["saved_lead_id"] = result["id"]
        return result

    def update_saved_lead(
        self,
        saved_lead_id: int,
        *,
        status: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, status, notes FROM saved_leads WHERE id = ?",
                (saved_lead_id,),
            ).fetchone()
            if not row:
                return None
            new_status = status or row["status"]
            new_notes = notes if notes is not None else row["notes"]
            conn.execute(
                "UPDATE saved_leads SET status = ?, notes = ?, updated_at = ? WHERE id = ?",
                (new_status, new_notes, now, saved_lead_id),
            )
            updated = conn.execute(
                "SELECT id, place_id, status, notes, lead_json, updated_at FROM saved_leads WHERE id = ?",
                (saved_lead_id,),
            ).fetchone()
            result = dict(updated)
            lead_data = json.loads(result["lead_json"])
            lead_data["status"] = result["status"]
            lead_data["notes"] = result["notes"]
            conn.execute(
                "UPDATE saved_leads SET lead_json = ? WHERE id = ?",
                (json.dumps(lead_data, ensure_ascii=False), saved_lead_id),
            )
        result.pop("lead_json", None)
        result["lead"] = lead_data
        return result

    def get_saved_leads_by_places(self, place_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not place_ids:
            return {}
        placeholders = ",".join("?" for _ in place_ids)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT id, place_id, status, notes FROM saved_leads WHERE place_id IN ({placeholders})",
                place_ids,
            ).fetchall()
        return {
            row["place_id"]: {
                "saved_lead_id": row["id"],
                "status": row["status"],
                "notes": row["notes"],
            }
            for row in rows
        }

    def list_saved_leads(self, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        query = """
            SELECT sl.id, sl.place_id, sl.status, sl.notes, sl.lead_json, sl.updated_at,
                   sh.project_id, sh.project_name, sh.business_type, sh.created_at AS search_at
            FROM saved_leads sl
            LEFT JOIN search_history sh ON sl.search_history_id = sh.id
        """
        params: list[Any] = []
        conditions: list[str] = []
        if status:
            conditions.append("sl.status = ?")
            params.append(status)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY sl.updated_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["lead"] = json.loads(item.pop("lead_json"))
            results.append(item)
        return results

    def list_saved_leads_admin(
        self,
        *,
        status: str | None = None,
        project_id: str | None = None,
        lead_fit: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT sl.id, sl.place_id, sl.status, sl.notes, sl.lead_json, sl.updated_at,
                   sh.project_id, sh.project_name, sh.business_type, sh.created_at AS search_at
            FROM saved_leads sl
            LEFT JOIN search_history sh ON sl.search_history_id = sh.id
        """
        params: list[Any] = []
        conditions: list[str] = []
        if status:
            conditions.append("sl.status = ?")
            params.append(status)
        if project_id:
            conditions.append(
                "(sh.project_id = ? OR json_extract(sl.lead_json, '$.recommended_project_id') = ?)"
            )
            params.extend([project_id, project_id])
        if lead_fit:
            conditions.append("json_extract(sl.lead_json, '$.lead_fit') = ?")
            params.append(lead_fit)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY sl.status ASC, sl.updated_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["lead"] = json.loads(item.pop("lead_json"))
            results.append(item)
        return results

    def count_leads_by_status(self) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS cnt FROM saved_leads GROUP BY status"
            ).fetchall()
        return {row["status"]: row["cnt"] for row in rows}

    def list_admin_project_filters(self) -> list[dict[str, str | None]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT sh.project_id, sh.project_name
                FROM saved_leads sl
                INNER JOIN search_history sh ON sl.search_history_id = sh.id
                WHERE sh.project_id IS NOT NULL OR sh.project_name IS NOT NULL
                ORDER BY sh.project_name COLLATE NOCASE
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def log_campaign_send(
        self,
        *,
        campaign: str,
        place_id: str,
        place_name: str | None,
        phone: str | None,
        zone: str | None,
        dry_run: bool,
        ok: bool,
        twilio_sid: str | None = None,
        twilio_status: str | None = None,
        error: str | None = None,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO campaign_sends (
                    campaign, place_id, place_name, phone, zone,
                    dry_run, ok, twilio_sid, twilio_status, error, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    campaign,
                    place_id,
                    place_name,
                    phone,
                    zone,
                    1 if dry_run else 0,
                    1 if ok else 0,
                    twilio_sid,
                    twilio_status,
                    error,
                    now,
                ),
            )
            return int(cur.lastrowid)

    def list_campaign_sends(
        self,
        campaign: str,
        *,
        limit: int = 200,
        only_live: bool = False,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT id, campaign, place_id, place_name, phone, zone,
                   dry_run, ok, twilio_sid, twilio_status, error, created_at
            FROM campaign_sends
            WHERE campaign = ?
        """
        params: list[Any] = [campaign]
        if only_live:
            query += " AND dry_run = 0"
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def list_sent_zones(self, campaign: str, *, live_only: bool = True) -> list[dict[str, Any]]:
        """Zonas / lugares con al menos un envío OK (agrupado)."""
        query = """
            SELECT
                COALESCE(NULLIF(TRIM(zone), ''), '(sin zona)') AS zone,
                COUNT(DISTINCT place_id) AS places,
                COUNT(*) AS sends,
                MAX(created_at) AS last_sent_at
            FROM campaign_sends
            WHERE campaign = ? AND ok = 1
        """
        params: list[Any] = [campaign]
        if live_only:
            query += " AND dry_run = 0"
        query += " GROUP BY COALESCE(NULLIF(TRIM(zone), ''), '(sin zona)') ORDER BY places DESC, zone COLLATE NOCASE"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def sent_place_ids_for_zone(
        self, campaign: str, zone: str, *, live_only: bool = True
    ) -> list[str]:
        z = (zone or "").strip()
        if not z or z == "(sin zona)":
            query = """
                SELECT DISTINCT place_id FROM campaign_sends
                WHERE campaign = ? AND ok = 1
                  AND (zone IS NULL OR TRIM(zone) = '')
            """
            params: list[Any] = [campaign]
        else:
            query = """
                SELECT DISTINCT place_id FROM campaign_sends
                WHERE campaign = ? AND ok = 1 AND TRIM(zone) = ?
            """
            params = [campaign, z]
        if live_only:
            query = query.replace("AND ok = 1", "AND ok = 1 AND dry_run = 0")
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [row["place_id"] for row in rows if row["place_id"]]

    def list_sent_zones_for_base(
        self,
        *,
        campaign_id: str,
        campaign_tag: str,
        base: str,
        live_only: bool = True,
    ) -> list[dict[str, Any]]:
        """Zonas con envío live, solo de leads de la base elegida."""
        base_name = (base or "").strip() or "Mendoza"
        query = """
            SELECT
                COALESCE(NULLIF(TRIM(cs.zone), ''), '(sin zona)') AS zone,
                COUNT(DISTINCT cs.place_id) AS places,
                COUNT(*) AS sends,
                MAX(cs.created_at) AS last_sent_at
            FROM campaign_sends cs
            INNER JOIN saved_leads sl ON sl.place_id = cs.place_id
            WHERE cs.campaign = ?
              AND cs.ok = 1
              AND json_extract(sl.lead_json, '$.campaign') = ?
              AND COALESCE(NULLIF(TRIM(json_extract(sl.lead_json, '$.base')), ''), 'Mendoza') = ?
        """
        params: list[Any] = [campaign_id, campaign_tag, base_name]
        if live_only:
            query += " AND cs.dry_run = 0"
        query += """
            GROUP BY COALESCE(NULLIF(TRIM(cs.zone), ''), '(sin zona)')
            ORDER BY places DESC, zone COLLATE NOCASE
        """
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def list_campaign_bases(self, campaign_tag: str) -> list[dict[str, Any]]:
        """Bases cargadas en CRM (lead_json.base) con totales."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    COALESCE(NULLIF(TRIM(json_extract(sl.lead_json, '$.base')), ''), 'Mendoza') AS base,
                    COUNT(*) AS leads
                FROM saved_leads sl
                WHERE json_extract(sl.lead_json, '$.campaign') = ?
                GROUP BY COALESCE(NULLIF(TRIM(json_extract(sl.lead_json, '$.base')), ''), 'Mendoza')
                ORDER BY leads DESC, base COLLATE NOCASE
                """,
                (campaign_tag,),
            ).fetchall()
        sent_ids = self.all_live_sent_place_ids()
        out: list[dict[str, Any]] = []
        for row in rows:
            base = row["base"]
            # cuántos de esta base ya tienen envío live
            with self._connect() as conn:
                place_rows = conn.execute(
                    """
                    SELECT sl.place_id
                    FROM saved_leads sl
                    WHERE json_extract(sl.lead_json, '$.campaign') = ?
                      AND COALESCE(NULLIF(TRIM(json_extract(sl.lead_json, '$.base')), ''), 'Mendoza') = ?
                    """,
                    (campaign_tag, base),
                ).fetchall()
            place_ids = {r["place_id"] for r in place_rows if r["place_id"]}
            sent = len(place_ids & sent_ids)
            out.append(
                {
                    "base": base,
                    "leads": int(row["leads"] or 0),
                    "sent": sent,
                    "pending": max(0, int(row["leads"] or 0) - sent),
                }
            )
        return out

    def campaign_sent_place_ids(self, campaign: str, *, live_only: bool = True) -> set[str]:
        query = """
            SELECT DISTINCT place_id FROM campaign_sends
            WHERE campaign = ? AND ok = 1
        """
        params: list[Any] = [campaign]
        if live_only:
            query += " AND dry_run = 0"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return {row["place_id"] for row in rows}

    def all_live_sent_place_ids(self) -> set[str]:
        """Place IDs con envío live OK en cualquier campaña (anti-reenvío entre bases)."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT place_id FROM campaign_sends
                WHERE ok = 1 AND dry_run = 0 AND place_id IS NOT NULL AND place_id != ''
                """
            ).fetchall()
        return {row["place_id"] for row in rows}

    def all_live_sent_phone_digits(self) -> set[str]:
        """Últimos 10 dígitos de teléfonos ya contactados live (anti-reenvío)."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT phone FROM campaign_sends
                WHERE ok = 1 AND dry_run = 0 AND phone IS NOT NULL AND phone != ''
                """
            ).fetchall()
        out: set[str] = set()
        for row in rows:
            digits = "".join(ch for ch in str(row["phone"] or "") if ch.isdigit())
            if len(digits) >= 10:
                out.add(digits[-10:])
            elif digits:
                out.add(digits)
        return out

    def campaign_send_stats(self, campaign: str) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_attempts,
                    SUM(CASE WHEN ok = 1 AND dry_run = 0 THEN 1 ELSE 0 END) AS live_ok,
                    SUM(CASE WHEN ok = 0 AND dry_run = 0 THEN 1 ELSE 0 END) AS live_fail,
                    SUM(CASE WHEN ok = 1 AND dry_run = 1 THEN 1 ELSE 0 END) AS dry_ok
                FROM campaign_sends
                WHERE campaign = ?
                """,
                (campaign,),
            ).fetchone()
        return {
            "total_attempts": int(rows["total_attempts"] or 0),
            "live_ok": int(rows["live_ok"] or 0),
            "live_fail": int(rows["live_fail"] or 0),
            "dry_ok": int(rows["dry_ok"] or 0),
        }

    def list_leads_by_campaign_tag(self, campaign_tag: str, limit: int = 2000) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT sl.id, sl.place_id, sl.status, sl.notes, sl.lead_json, sl.updated_at,
                       sh.project_id, sh.project_name, sh.business_type, sh.created_at AS search_at
                FROM saved_leads sl
                LEFT JOIN search_history sh ON sl.search_history_id = sh.id
                WHERE json_extract(sl.lead_json, '$.campaign') = ?
                ORDER BY sl.updated_at DESC
                LIMIT ?
                """,
                (campaign_tag, limit),
            ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["lead"] = json.loads(item.pop("lead_json"))
            results.append(item)
        return results

    def count_leads_by_campaign_status(self, campaign_tag: str) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT sl.status, COUNT(*) AS cnt
                FROM saved_leads sl
                WHERE json_extract(sl.lead_json, '$.campaign') = ?
                GROUP BY sl.status
                """,
                (campaign_tag,),
            ).fetchall()
        return {row["status"]: row["cnt"] for row in rows}

    def log_campaign_message(
        self,
        *,
        campaign: str,
        place_id: str | None,
        phone: str,
        direction: str,
        body: str | None,
        twilio_sid: str | None = None,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO campaign_messages (
                    campaign, place_id, phone, direction, body, twilio_sid, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (campaign, place_id, phone, direction, body, twilio_sid, now),
            )
            return int(cur.lastrowid)

    def list_campaign_messages(
        self,
        campaign: str,
        *,
        place_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT id, campaign, place_id, phone, direction, body, twilio_sid, created_at
            FROM campaign_messages
            WHERE campaign = ?
        """
        params: list[Any] = [campaign]
        if place_id:
            query += " AND place_id = ?"
            params.append(place_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def find_lead_by_phone_digits(self, digits: str) -> dict[str, Any] | None:
        """Busca lead por teléfono (últimos 10 dígitos). Prioriza destinatarios de envío live."""
        if not digits:
            return None
        needle = digits[-10:] if len(digits) >= 10 else digits
        if len(needle) < 8:
            return None

        def _phone_match(phone: str | None) -> bool:
            ph = "".join(ch for ch in str(phone or "") if ch.isdigit())
            if len(ph) < 8:
                return False
            tail = ph[-10:] if len(ph) >= 10 else ph
            return ph.endswith(needle) or needle.endswith(tail)

        # 1) Destinatarios reales de Twilio (más fiable que CRM sin teléfono)
        with self._connect() as conn:
            send_rows = conn.execute(
                """
                SELECT place_id, phone FROM campaign_sends
                WHERE ok = 1 AND dry_run = 0
                  AND place_id IS NOT NULL AND place_id != ''
                  AND phone IS NOT NULL AND phone != ''
                ORDER BY id DESC
                LIMIT 3000
                """
            ).fetchall()
        for srow in send_rows:
            if not _phone_match(srow["phone"]):
                continue
            place_id = srow["place_id"]
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT id, place_id, status, notes, lead_json, updated_at
                    FROM saved_leads WHERE place_id = ?
                    ORDER BY updated_at DESC LIMIT 1
                    """,
                    (place_id,),
                ).fetchone()
            if row:
                item = dict(row)
                item["lead"] = json.loads(item.pop("lead_json"))
                return item

        # 2) Fallback CRM: solo leads con teléfono real (nunca phone vacío)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, place_id, status, notes, lead_json, updated_at
                FROM saved_leads
                WHERE lead_json LIKE '%phone%'
                ORDER BY updated_at DESC
                LIMIT 5000
                """
            ).fetchall()
        best: dict[str, Any] | None = None
        for row in rows:
            lead = json.loads(row["lead_json"])
            if not _phone_match(lead.get("phone")):
                continue
            item = dict(row)
            item["lead"] = lead
            item.pop("lead_json", None)
            # Preferir leads de campaña / contactados
            if (lead.get("campaign") or "") or row["status"] in (
                "contacted",
                "responded",
                "follow_up",
            ):
                return item
            if best is None:
                best = item
        return best

    def list_campaign_leads_by_status(
        self, campaign_tag: str, status: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT sl.id, sl.place_id, sl.status, sl.notes, sl.lead_json, sl.updated_at
                FROM saved_leads sl
                WHERE json_extract(sl.lead_json, '$.campaign') = ?
                  AND sl.status = ?
                ORDER BY sl.updated_at DESC
                LIMIT ?
                """,
                (campaign_tag, status, limit),
            ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["lead"] = json.loads(item.pop("lead_json"))
            results.append(item)
        return results

    def list_responded_campaign_leads(self, campaign_tag: str, limit: int = 100) -> list[dict[str, Any]]:
        return self.list_campaign_leads_by_status(campaign_tag, "responded", limit=limit)

    @staticmethod
    def _row_to_profile(row: sqlite3.Row) -> ServiceProfile:
        return ServiceProfile(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            lead_criteria=row["lead_criteria"],
            suggested_business_types=json.loads(row["suggested_business_types"]),
        )
