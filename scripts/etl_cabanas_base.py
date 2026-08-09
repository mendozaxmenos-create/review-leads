"""ETL genérico multi-base: classify + phone + filtro reservas online.

Uso:
  .venv\\Scripts\\python -m scripts.etl_cabanas_base --base "Salta"
  .venv\\Scripts\\python -m scripts.etl_cabanas_base --base Mendoza --in data/exports/mendoza-cabanas-ready.csv
  .venv\\Scripts\\python -m scripts.etl_cabanas_base --base Córdoba --fetch-booking
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.data.cabanas_filter import classify_cabana_lead  # noqa: E402
from app.services.booking_signals import classify_website_url  # noqa: E402

EXPORT = ROOT / "data" / "exports"

KEEP_DESPITE_LABEL_HINTS = (
    "cabaña",
    "cabana",
    "cabañas",
    "cabanas",
    "complejo",
)

# Blocklists solo Mendoza
_MENDOZA_BLOCKED_NAMES = ("villa oliva", "villaoliva")
_MENDOZA_BLOCKED_ZONES = ("las lenas", "las leñas")


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFD", (text or "").lower().strip())
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def digits_only(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def normalize_phone_e164(phone: str) -> tuple[str | None, str | None]:
    d = digits_only(phone)
    if not d:
        return None, "sin_digitos"
    if d.startswith("54"):
        rest = d[2:]
    elif d.startswith("0"):
        rest = d.lstrip("0")
    else:
        rest = d
    if len(rest) == 10 and not rest.startswith("9"):
        return f"+54{rest}", None
    if len(rest) == 11 and rest.startswith("9"):
        return f"+54{rest}", None
    if len(rest) == 10 and rest.startswith("9"):
        return f"+54{rest}", "largo_dudoso"
    if len(d) == 9 or len(rest) < 10:
        return None, f"telefono_corto_{len(d)}_digitos"
    if len(rest) > 11:
        return None, f"telefono_largo_{len(d)}_digitos"
    return f"+54{rest}", "formato_revisar"


def extract_zone(reason: str) -> str:
    m = re.match(r"\[([^\]]+)\]", (reason or "").strip())
    return m.group(1).strip() if m else ""


def hard_exclude(row: dict, *, base_name: str) -> str | None:
    name_n = _norm(row.get("place_name") or "")
    label_n = _norm(row.get("business_type_label") or "")
    address_n = _norm(row.get("address") or "")
    zone_n = _norm(extract_zone(row.get("reason") or "") or row.get("zone") or "")
    has_cabana_name = any(h in name_n for h in KEEP_DESPITE_LABEL_HINTS)
    base_cf = (base_name or "").casefold()

    if "mendoza" in base_cf:
        for blocked in _MENDOZA_BLOCKED_NAMES:
            if blocked in name_n:
                return f"blocked_{blocked.replace(' ', '_')}"
        for bz in _MENDOZA_BLOCKED_ZONES:
            if bz in zone_n or bz in name_n or bz in address_n:
                return f"zona_bloqueada_{bz.replace(' ', '_')}"

    always_out = {
        "restaurantes",
        "service",
        "travel agency",
        "rest stop",
        "farmstay",
        "picnic ground",
    }
    if label_n in always_out:
        return f"label_{label_n.replace(' ', '_')}"

    if label_n in {"hostels", "camping"}:
        if has_cabana_name and "hostel" not in name_n and "hostal" not in name_n and "camping" not in name_n:
            pass
        else:
            return f"label_{label_n}"

    if "hostel" in name_n or "hostal" in name_n:
        return "nombre_hostel"
    if "restaurante" in name_n or "parrilla" in name_n:
        if not has_cabana_name:
            return "nombre_gastronomia"

    return None


def score_row(row: dict, *, booking_soft: int = 0) -> int:
    score = 0
    if (row.get("phone") or "").strip():
        score += 2
    if (row.get("website") or "").strip():
        score += 1
    if (row.get("rating") or "").strip():
        score += 1
    lab = _norm(row.get("business_type_label") or "")
    if "caba" in lab or "guest" in lab or "apart" in lab:
        score += 2
    if "hotel" in lab or "resort" in lab:
        score -= 1
    # Preferir sin motor online: soft_penalty resta
    score -= int(booking_soft or 0)
    # Sin website = más ICP WhatsApp
    if not (row.get("website") or "").strip():
        score += 1
    return score


def _slug_base(base_name: str) -> str:
    raw = (base_name or "base").strip()
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in raw)[:48] or "base"


def _default_input_for_base(base_name: str) -> Path | None:
    """Busca el raw/ready más reciente o conocido para la base."""
    slug = _slug_base(base_name)
    cf = base_name.casefold()
    candidates: list[Path] = []
    if "mendoza" in cf:
        candidates += [
            EXPORT / "mendoza-cabanas-ready.csv",
            EXPORT / "mendoza-cabanas-etl-clean.csv",
        ]
    if "córdoba" in cf or "cordoba" in cf:
        candidates += [
            EXPORT / "cordoba-cabanas-ready.csv",
            EXPORT / "cordoba-cabanas-etl-clean.csv",
            EXPORT / "campaign-Córdoba.csv",
        ]
    candidates.append(EXPORT / f"campaign-{base_name}.csv")
    candidates.append(EXPORT / f"campaign-{slug}.csv")
    # últimos sweeps
    for pattern in (f"{slug}-cabanas-*.csv", f"*{slug}*cabanas*.csv"):
        candidates.extend(sorted(EXPORT.glob(pattern), reverse=True)[:3])
    # generic sweep naming: buenos-aires-interior-cabanas-TIMESTAMP.csv
    for p in sorted(EXPORT.glob("*-cabanas-2*.csv"), reverse=True):
        if slug.split("-")[0].lower() in p.name.lower() or _norm(base_name)[:6] in _norm(p.name):
            candidates.append(p)
    for p in candidates:
        if p.exists() and "quarantine" not in p.name and "report" not in p.name:
            return p
    return None


def run_etl(
    *,
    base_name: str,
    src: Path,
    fetch_booking: bool = True,
) -> dict:
    with src.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    issue_counts: Counter[str] = Counter()
    quarantine: list[dict] = []
    clean: list[dict] = []
    issues: list[dict] = []

    for row in rows:
        out = dict(row)
        zone = out.get("zone") or extract_zone(out.get("reason") or "")
        out["zone"] = zone
        out["base"] = base_name

        hexcl = hard_exclude(out, base_name=base_name)
        out["hard_exclude"] = hexcl or ""
        if hexcl:
            issue_counts[hexcl] += 1
            quarantine.append({**out, "etl_status": "quarantine", "etl_reason": hexcl})
            issues.append(
                {"place_id": out.get("place_id"), "place_name": out.get("place_name"), "issue": hexcl}
            )
            continue

        ok, reason = classify_cabana_lead(out)
        out["reclassify_ok"] = "yes" if ok else "no"
        out["reclassify_reason"] = reason or ""
        if not ok:
            issue_counts[f"reclassify_{reason or 'fail'}"] += 1
            quarantine.append(
                {**out, "etl_status": "quarantine", "etl_reason": f"reclassify:{reason}"}
            )
            issues.append(
                {
                    "place_id": out.get("place_id"),
                    "place_name": out.get("place_name"),
                    "issue": f"reclassify:{reason}",
                }
            )
            continue

        e164, phone_err = normalize_phone_e164(out.get("phone") or "")
        out["phone_e164"] = e164 or ""
        out["phone_error"] = phone_err or ""
        if phone_err in ("sin_digitos",) or (phone_err and phone_err.startswith("telefono_corto")):
            issue_counts[phone_err or "phone_bad"] += 1
            quarantine.append({**out, "etl_status": "quarantine", "etl_reason": phone_err})
            issues.append(
                {"place_id": out.get("place_id"), "place_name": out.get("place_name"), "issue": phone_err}
            )
            continue

        # Filtro reservas online (hard)
        bsig = classify_website_url(out.get("website"), fetch_html=fetch_booking)
        out["has_online_booking"] = "yes" if bsig.has_online_booking else "no"
        out["booking_signal"] = bsig.signal
        if bsig.has_online_booking:
            issue_counts["online_booking"] += 1
            quarantine.append(
                {
                    **out,
                    "etl_status": "quarantine",
                    "etl_reason": f"online_booking:{bsig.signal}",
                }
            )
            issues.append(
                {
                    "place_id": out.get("place_id"),
                    "place_name": out.get("place_name"),
                    "issue": f"online_booking:{bsig.signal}",
                }
            )
            continue

        out["etl_score"] = str(score_row(out, booking_soft=bsig.soft_penalty))
        clean.append({**out, "etl_status": "clean", "etl_reason": ""})

    by_phone: dict[str, list[dict]] = defaultdict(list)
    for row in clean:
        key = row.get("phone_e164") or digits_only(row.get("phone") or "")
        by_phone[key].append(row)

    deduped: list[dict] = []
    dup_dropped = 0
    for _phone, group in by_phone.items():
        if len(group) == 1:
            deduped.append(group[0])
            continue
        group_sorted = sorted(group, key=lambda r: int(r.get("etl_score") or 0), reverse=True)
        winner = group_sorted[0]
        winner["etl_reason"] = f"dedupe_phone_kept; rivals={[g.get('place_name') for g in group_sorted[1:]]}"
        deduped.append(winner)
        for loser in group_sorted[1:]:
            dup_dropped += 1
            issue_counts["dedupe_phone"] += 1
            quarantine.append(
                {
                    **loser,
                    "etl_status": "quarantine",
                    "etl_reason": f"dedupe_phone_lost_to:{winner.get('place_name')}",
                }
            )

    # Prefer higher score first (send priority)
    deduped.sort(key=lambda r: int(r.get("etl_score") or 0), reverse=True)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    EXPORT.mkdir(parents=True, exist_ok=True)
    slug = _slug_base(base_name)
    clean_path = EXPORT / f"campaign-{base_name}.csv"
    clean_alias = EXPORT / f"{slug}-cabanas-etl-clean.csv"
    clean_stamped = EXPORT / f"{slug}-cabanas-etl-clean-{stamp}.csv"
    quar_path = EXPORT / f"{slug}-cabanas-etl-quarantine.csv"
    report_path = EXPORT / f"{slug}-cabanas-etl-report.json"

    # Mendoza legacy filenames
    if "mendoza" in base_name.casefold():
        clean_alias = EXPORT / "mendoza-cabanas-etl-clean.csv"
        quar_path = EXPORT / "mendoza-cabanas-etl-quarantine.csv"
        report_path = EXPORT / "mendoza-cabanas-etl-report.json"

    extra_fields = [
        "phone_e164",
        "phone_error",
        "zone",
        "base",
        "reclassify_ok",
        "reclassify_reason",
        "hard_exclude",
        "has_online_booking",
        "booking_signal",
        "etl_score",
        "etl_status",
        "etl_reason",
    ]
    out_fields = fieldnames + [f for f in extra_fields if f not in fieldnames]

    def write_csv(path: Path, data: list[dict]) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=out_fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(data)

    for row in deduped:
        if row.get("phone_e164"):
            row["phone"] = row["phone_e164"]

    write_csv(clean_path, deduped)
    write_csv(clean_alias, deduped)
    write_csv(clean_stamped, deduped)
    write_csv(quar_path, quarantine)

    if "córdoba" in base_name.casefold() or "cordoba" in base_name.casefold():
        write_csv(EXPORT / "cordoba-cabanas-etl-clean.csv", deduped)
        write_csv(EXPORT / "campaign-Córdoba.csv", deduped)

    report = {
        "base": base_name,
        "source": str(src),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "input_rows": len(rows),
        "clean_rows": len(deduped),
        "quarantine_rows": len(quarantine),
        "dup_phones_dropped": dup_dropped,
        "online_booking_rejected": issue_counts.get("online_booking", 0),
        "fetch_booking": fetch_booking,
        "issue_counts": dict(issue_counts.most_common()),
        "outputs": {
            "clean": str(clean_path),
            "clean_alias": str(clean_alias),
            "quarantine": str(quar_path),
            "report": str(report_path),
        },
        "zones_clean": dict(Counter(r.get("zone") or "?" for r in deduped).most_common()),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    from app.data.ar_locations import CABANAS_BASES, list_cabanas_base_names

    parser = argparse.ArgumentParser(description="ETL cabañas multi-base + filtro booking")
    parser.add_argument("--base", required=True, help=f"Base CRM. Válidas: {', '.join(list_cabanas_base_names())}")
    parser.add_argument("--in", dest="src", default="", help="CSV de entrada (raw/ready)")
    parser.add_argument(
        "--fetch-booking",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fetch homepage para detectar motor (default: sí)",
    )
    parser.add_argument(
        "--sync-crm",
        action="store_true",
        help="Tras ETL, sync clean → CRM y descartar online_booking en CRM",
    )
    args = parser.parse_args()

    base = args.base.strip()
    if base not in CABANAS_BASES and not any(b.casefold() == base.casefold() for b in CABANAS_BASES):
        # allow free-form base names for re-etl of custom labels
        pass
    else:
        # normalize casing to registry key
        for name in CABANAS_BASES:
            if name.casefold() == base.casefold():
                base = name
                break

    src = Path(args.src) if args.src else _default_input_for_base(base)
    if not src or not src.exists():
        print(f"No hay CSV de entrada para «{base}». Pasá --in ruta.csv", file=sys.stderr)
        return 1

    print(f"ETL base={base} src={src} fetch_booking={args.fetch_booking}", flush=True)
    report = run_etl(base_name=base, src=src, fetch_booking=args.fetch_booking)
    print(
        f"Input={report['input_rows']} Clean={report['clean_rows']} "
        f"Quarantine={report['quarantine_rows']} "
        f"online_booking={report['online_booking_rejected']}",
        flush=True,
    )
    for k, v in list(report["issue_counts"].items())[:15]:
        print(f"  - {k}: {v}", flush=True)
    print(f"Clean: {report['outputs']['clean']}", flush=True)

    if args.sync_crm:
        from app.services.mendoza_campaign import sync_etl_clean_to_crm
        from scripts.mark_booking_discards import mark_quarantine_booking_discarded

        sync = sync_etl_clean_to_crm(
            csv_path=Path(report["outputs"]["clean"]),
            base_name=base,
        )
        print(f"CRM sync: {sync}", flush=True)
        discarded = mark_quarantine_booking_discarded(Path(report["outputs"]["quarantine"]))
        print(f"CRM discarded (online booking): {discarded}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
