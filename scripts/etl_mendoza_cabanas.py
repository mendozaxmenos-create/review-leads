"""ETL / auditoría de la base Mendoza · cabañas ready.

Uso:
  .venv\\Scripts\\python -m scripts.etl_mendoza_cabanas
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

EXPORT = ROOT / "data" / "exports"

HARD_EXCLUDE_LABELS = {
    "restaurantes",
    "hostels",
    "camping",
    "picnic ground",
    "service",
    "travel agency",
    "rest stop",
    "farmstay",
}

HARD_EXCLUDE_NAME = (
    "hostel",
    "hostal",
    "restaurante",
    "parrilla",
)

# Cliente / competencia: no prospectar
BLOCKED_PLACE_NAMES = (
    "villa oliva",
    "villaoliva",
)

# Zonas fuera de campaña (ej. ski / no foco)
BLOCKED_ZONES = (
    "las leñas",
    "las lenas",
)

# Si el nombre dice cabaña/complejo, no excluir solo por label Hostels/Camping
KEEP_DESPITE_LABEL_HINTS = (
    "cabaña",
    "cabana",
    "cabañas",
    "cabanas",
    "complejo",
)


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFD", (text or "").lower().strip())
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def digits_only(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def normalize_phone_e164(phone: str) -> tuple[str | None, str | None]:
    """Devuelve (e164, error)."""
    d = digits_only(phone)
    if not d:
        return None, "sin_digitos"
    if d.startswith("54"):
        rest = d[2:]
    elif d.startswith("0"):
        rest = d.lstrip("0")
    else:
        rest = d

    # Móvil AR: 9 + área + número → total 10 o 11 después del 54
    # Fijo: área + número
    if len(rest) == 10 and not rest.startswith("9"):
        # posible fijo: 261 XXXXXXX
        e164 = f"+54{rest}"
        return e164, None
    if len(rest) == 11 and rest.startswith("9"):
        e164 = f"+54{rest}"
        return e164, None
    if len(rest) == 10 and rest.startswith("9"):
        # ya con 9 pero corto?
        e164 = f"+54{rest}"
        return e164, "largo_dudoso"
    if len(d) == 9 or len(rest) < 10:
        return None, f"telefono_corto_{len(d)}_digitos"
    if len(rest) > 11:
        return None, f"telefono_largo_{len(d)}_digitos"
    e164 = f"+54{rest}"
    return e164, "formato_revisar"


def extract_zone(reason: str) -> str:
    m = re.match(r"\[([^\]]+)\]", (reason or "").strip())
    return m.group(1).strip() if m else ""


def hard_exclude(row: dict) -> str | None:
    name_n = _norm(row.get("place_name") or "")
    label_n = _norm(row.get("business_type_label") or "")
    address_n = _norm(row.get("address") or "")
    zone_n = _norm(extract_zone(row.get("reason") or ""))
    has_cabana_name = any(h in name_n for h in KEEP_DESPITE_LABEL_HINTS)

    for blocked in BLOCKED_PLACE_NAMES:
        if blocked in name_n:
            return "blocked_villa_oliva"

    for blocked_zone in BLOCKED_ZONES:
        bz = _norm(blocked_zone)
        if zone_n == bz or bz in zone_n:
            return "zona_las_lenas"
        if bz in name_n or bz in address_n:
            return "zona_las_lenas"

    # Labels no confiables / no target: siempre fuera
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

    # Hostels / camping: fuera salvo nombre claramente cabaña y sin hostel/camping
    if label_n in {"hostels", "camping"}:
        if has_cabana_name and "hostel" not in name_n and "hostal" not in name_n and "camping" not in name_n:
            return None
        return f"label_{label_n}"

    if "hostel" in name_n or "hostal" in name_n:
        return "hostel_en_nombre"
    if "restaurante" in name_n or "parrilla" in name_n:
        return "gastronomia_en_nombre"
    return None


def score_row(row: dict) -> int:
    """Mayor = mejor para conservar en dedupe."""
    score = 0
    name = _norm(row.get("place_name") or "")
    label = _norm(row.get("business_type_label") or "")
    if "caba" in name:
        score += 5
    if label in ("cabañas", "cabanas", "casas de huespedes", "bed & breakfast", "alojamiento"):
        score += 3
    if label in ("hoteles", "resorts"):
        score -= 1
    if (row.get("website") or "").strip():
        score += 1
    try:
        rating = float(row.get("rating") or 0)
        score += int(rating)
    except ValueError:
        pass
    return score


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--csv",
        default=str(EXPORT / "mendoza-cabanas-ready.csv"),
        help="CSV de entrada (ready)",
    )
    args = parser.parse_args()
    src = Path(args.csv)
    if not src.exists():
        print(f"No existe {src}")
        return 1

    with src.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    issues: list[dict] = []
    clean: list[dict] = []
    quarantine: list[dict] = []
    issue_counts: Counter[str] = Counter()

    enriched: list[dict] = []
    for row in rows:
        out = dict(row)
        e164, phone_err = normalize_phone_e164(row.get("phone") or "")
        out["phone_e164"] = e164 or ""
        out["phone_error"] = phone_err or ""
        out["zone"] = extract_zone(row.get("reason") or "")
        ok, reason = classify_cabana_lead(row)
        out["reclassify_ok"] = "yes" if ok else "no"
        out["reclassify_reason"] = reason
        hard = hard_exclude(row)
        out["hard_exclude"] = hard or ""
        out["etl_score"] = str(score_row(row))
        enriched.append(out)

        if hard:
            issue_counts[hard] += 1
            quarantine.append({**out, "etl_status": "quarantine", "etl_reason": hard})
            issues.append({"place_id": out.get("place_id"), "place_name": out.get("place_name"), "issue": hard})
            continue
        if not ok:
            issue_counts[f"reclassify_{reason}"] += 1
            quarantine.append({**out, "etl_status": "quarantine", "etl_reason": reason})
            issues.append({"place_id": out.get("place_id"), "place_name": out.get("place_name"), "issue": reason})
            continue
        if phone_err in ("sin_digitos",) or (phone_err and phone_err.startswith("telefono_corto")):
            issue_counts[phone_err or "phone_bad"] += 1
            quarantine.append({**out, "etl_status": "quarantine", "etl_reason": phone_err})
            issues.append(
                {"place_id": out.get("place_id"), "place_name": out.get("place_name"), "issue": phone_err}
            )
            continue
        clean.append({**out, "etl_status": "clean", "etl_reason": ""})

    # Dedup por teléfono E.164
    by_phone: dict[str, list[dict]] = defaultdict(list)
    for row in clean:
        key = row.get("phone_e164") or digits_only(row.get("phone") or "")
        by_phone[key].append(row)

    deduped: list[dict] = []
    dup_dropped = 0
    for phone, group in by_phone.items():
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
            issues.append(
                {
                    "place_id": loser.get("place_id"),
                    "place_name": loser.get("place_name"),
                    "issue": "dedupe_phone",
                    "kept": winner.get("place_name"),
                }
            )

    # Warnings (no quarantine): weird labels, empty rating
    warnings: list[dict] = []
    for row in deduped:
        lab = row.get("business_type_label") or ""
        if lab in ("Service", "Travel Agency", "Rest Stop", "Farmstay"):
            warnings.append(
                {
                    "place_id": row.get("place_id"),
                    "place_name": row.get("place_name"),
                    "warning": f"label_raro:{lab}",
                }
            )
            issue_counts["warn_label_raro"] += 1
        if not (row.get("rating") or "").strip():
            warnings.append(
                {
                    "place_id": row.get("place_id"),
                    "place_name": row.get("place_name"),
                    "warning": "sin_rating",
                }
            )
            issue_counts["warn_sin_rating"] += 1
        if row.get("phone_error") and row["phone_error"] not in ("",):
            warnings.append(
                {
                    "place_id": row.get("place_id"),
                    "place_name": row.get("place_name"),
                    "warning": f"phone:{row['phone_error']}",
                }
            )

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    EXPORT.mkdir(parents=True, exist_ok=True)
    clean_path = EXPORT / "mendoza-cabanas-etl-clean.csv"
    clean_stamped = EXPORT / f"mendoza-cabanas-etl-clean-{stamp}.csv"
    quar_path = EXPORT / "mendoza-cabanas-etl-quarantine.csv"
    report_path = EXPORT / "mendoza-cabanas-etl-report.json"

    out_fields = fieldnames + [
        f
        for f in (
            "phone_e164",
            "phone_error",
            "zone",
            "reclassify_ok",
            "reclassify_reason",
            "hard_exclude",
            "etl_score",
            "etl_status",
            "etl_reason",
        )
        if f not in fieldnames
    ]

    def write_csv(path: Path, data: list[dict]) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=out_fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(data)

    # Prefer phone_e164 as phone for campaign
    for row in deduped:
        if row.get("phone_e164"):
            row["phone"] = row["phone_e164"]

    write_csv(clean_path, deduped)
    write_csv(clean_stamped, deduped)
    write_csv(quar_path, quarantine)

    # Also refresh ready alias used by send script? Keep ready as-is; send can use etl-clean.
    report = {
        "source": str(src),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "input_rows": len(rows),
        "clean_rows": len(deduped),
        "quarantine_rows": len(quarantine),
        "dup_phones_dropped": dup_dropped,
        "issue_counts": dict(issue_counts.most_common()),
        "warnings_count": len(warnings),
        "warnings_sample": warnings[:40],
        "issues_sample": issues[:40],
        "outputs": {
            "clean": str(clean_path),
            "quarantine": str(quar_path),
            "report": str(report_path),
        },
        "label_breakdown_clean": dict(Counter(r.get("business_type_label") for r in deduped).most_common()),
        "zones_clean": dict(Counter(r.get("zone") or "?" for r in deduped).most_common()),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Input: {len(rows)}")
    print(f"Clean: {len(deduped)}")
    print(f"Quarantine: {len(quarantine)} (dup phones dropped: {dup_dropped})")
    print("Issues:")
    for k, v in issue_counts.most_common():
        print(f"  - {k}: {v}")
    print(f"Clean CSV: {clean_path}")
    print(f"Quarantine CSV: {quar_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
