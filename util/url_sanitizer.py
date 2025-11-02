"""Hilfsfunktionen zur Bereinigung externer Produkt-URLs."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_ALLOWED_BAUHAUS_DOMAINS = (
    "bauhaus.info",
    "bauhaus.de",
    "bauhaus.at",
)

_EXACT_BLOCKED_PARAMS = {"fbclid", "gclid", "ref", "utm"}


def clean_product_url(url: str) -> str:
    """Sanitizes Bauhaus-Produktlinks und entfernt Tracking-Parameter."""

    if not url or not url.strip():
        raise ValueError("URL darf nicht leer sein")

    candidate = url.strip()
    if not candidate.startswith("http"):
        candidate = "https://" + candidate.lstrip("/")

    parsed = urlparse(candidate)
    if not parsed.netloc:
        raise ValueError("URL enthaelt keine gueltige Domain")

    host = parsed.netloc.lower()
    matching_domain = next((domain for domain in _ALLOWED_BAUHAUS_DOMAINS if host.endswith(domain)), None)
    if not matching_domain:
        raise ValueError("Nur Bauhaus-Domains sind erlaubt")

    normalized_host = f"www.{matching_domain}" if not host.startswith("www.") else host

    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not _is_tracking_param(key)
    ]

    cleaned = parsed._replace(
        netloc=normalized_host,
        query=urlencode(filtered_query, doseq=True),
        fragment="",
    )
    return urlunparse(cleaned)


def _is_tracking_param(key: str) -> bool:
    lowered = key.lower()
    if lowered in _EXACT_BLOCKED_PARAMS:
        return True
    if lowered.startswith("utm_"):
        return True
    if lowered.startswith("mc_"):
        return True
    if lowered.startswith("ref_"):
        return True
    return False


__all__ = ["clean_product_url"]

