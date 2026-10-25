"""Normalise database URLs from hosting providers (pure Python)."""
from __future__ import annotations


def normalize_database_url(url: str) -> str:
    """Hosted Postgres providers hand out `postgres://` or `postgresql://` URLs. SQLAlchemy needs the
    driver named explicitly; this project ships psycopg 3, so use `postgresql+psycopg://`."""
    url = (url or "").strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url
