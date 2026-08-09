"""Detecta si un alojamiento ya tiene canal fuerte de reservas online (OTA / motor)."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

# Dominios OTA / directorios de reserva (hard exclude)
_OTA_HOST_PARTS = (
    "booking.com",
    "airbnb.",
    "despegar.",
    "expedia.",
    "hotels.com",
    "tripadvisor.",
    "trivago.",
    "kayak.",
    "hostelworld.",
    "agoda.",
    "vrbo.",
    "homeaway.",
    "alojamiento.com",
    "cabanas.com.ar",
    "cabañas.com.ar",
    "bookingengine",
)

# Motores / PMS embebidos (URL o HTML)
_ENGINE_HINTS = (
    "littlehotelier",
    "cloudbeds",
    "mews.com",
    "wubook",
    "roomcloud",
    "minihotel",
    "hotelrunner",
    "site.com.ar",
    "reservas.",
    "booking-engine",
    "book-now",
    "engine/book",
    "/reservar",
    "/reservation",
    "/booking",
    "guesty",
    "hostaway",
    "lodgify",
    "smoobu",
)

# HTML snippets que indican motor de reservas usable
_HTML_ENGINE_RE = re.compile(
    r"("
    r"booking\.com/hotel|"
    r"airbnb\.com/rooms|"
    r"despegar\.com|"
    r"littlehotelier|"
    r"cloudbeds|"
    r"wubook|"
    r"roomcloud|"
    r"hotelrunner|"
    r"mews\.com|"
    r"data-booking|"
    r"book-now|"
    r"reservar\s+ahora|"
    r"online.?booking.?engine|"
    r"iframe[^>]*(booking|reserv)"
    r")",
    re.I,
)

# Sitios que NO son booking fuerte (ICP: solo consulta / redes)
_WEAK_HOST_PARTS = (
    "instagram.com",
    "facebook.com",
    "fb.com",
    "linktr.ee",
    "wa.me",
    "api.whatsapp.com",
    "google.com",
    "maps.app.goo.gl",
    "youtu",
    "tiktok.com",
)

_host_cache: dict[str, tuple[float, "BookingSignal"]] = {}
_CACHE_TTL_SEC = 7 * 24 * 3600


@dataclass(frozen=True)
class BookingSignal:
    has_online_booking: bool
    signal: str  # razón corta
    soft_penalty: int = 0  # para score ETL (0–2)


def _host(url: str) -> str:
    try:
        p = urlparse(url if "://" in url else f"https://{url}")
        return (p.netloc or "").lower().removeprefix("www.")
    except Exception:
        return ""


def classify_website_url(website: str | None, *, fetch_html: bool = True) -> BookingSignal:
    """Hard exclude si OTA/motor; soft penalty si sitio corporativo sin señal clara."""
    raw = (website or "").strip()
    if not raw:
        return BookingSignal(False, "no_website", soft_penalty=0)

    low = raw.lower()
    host = _host(raw)
    if not host:
        return BookingSignal(False, "website_invalid", soft_penalty=0)

    if any(w in host for w in _WEAK_HOST_PARTS):
        return BookingSignal(False, "weak_social_or_maps", soft_penalty=0)

    if any(p in host or p in low for p in _OTA_HOST_PARTS):
        return BookingSignal(True, f"ota_or_directory:{host}", soft_penalty=2)

    if any(h in low for h in _ENGINE_HINTS):
        return BookingSignal(True, f"booking_engine_url:{host}", soft_penalty=2)

    if not fetch_html:
        # Sitio propio sin pista en URL: no excluir; leve soft
        return BookingSignal(False, "own_site_unchecked", soft_penalty=1)

    cached = _host_cache.get(host)
    now = time.time()
    if cached and now - cached[0] < _CACHE_TTL_SEC:
        return cached[1]

    signal = _fetch_homepage_signal(raw, host)
    _host_cache[host] = (now, signal)
    return signal


def _fetch_homepage_signal(url: str, host: str) -> BookingSignal:
    target = url if "://" in url else f"https://{url}"
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=5.0,
            headers={"User-Agent": "SofIA-lead-audit/1.0 (+https://review-leads.onrender.com)"},
        ) as client:
            r = client.get(target)
            final = str(r.url).lower()
            if any(p in final or p in _host(final) for p in _OTA_HOST_PARTS):
                return BookingSignal(True, f"redirect_ota:{_host(final)}", soft_penalty=2)
            text = (r.text or "")[:120_000]
            if _HTML_ENGINE_RE.search(text):
                return BookingSignal(True, f"html_engine:{host}", soft_penalty=2)
            if any(h in text.lower() for h in ("littlehotelier", "cloudbeds", "wubook", "roomcloud")):
                return BookingSignal(True, f"html_pms:{host}", soft_penalty=2)
    except Exception:
        # Fallo de red: no excluir
        return BookingSignal(False, "fetch_failed", soft_penalty=1)

    return BookingSignal(False, "own_site_ok", soft_penalty=1)
