"""Accept-Language resolution (reuses app.core.i18n)."""
from fastapi import Header

from app.core.i18n import DEFAULT_LANGUAGE, recognised_language


def _candidates(header: str | None):
    for i, part in enumerate((header or "").split(",")):
        tag, _, params = part.strip().partition(";")
        q = 1.0
        for p in params.split(";"):
            k, _, v = p.strip().partition("=")
            if k.strip().lower() == "q":
                try:
                    q = float(v)
                except ValueError:
                    q = 0.0
        if tag.strip() and q > 0:
            yield -q, i, tag.strip()


def header_language(header: str | None) -> str | None:
    """Best recognised en/rw tag by q-value, else None."""
    for _, _, tag in sorted(_candidates(header)):
        if (lang := recognised_language(tag)):
            return lang
    return None


def parse_accept_language(header: str | None) -> str:
    return header_language(header) or DEFAULT_LANGUAGE


async def accept_language(accept_language: str | None = Header(None)) -> str | None:
    """Dependency: recognised header language, or None (let the service use its own default)."""
    return header_language(accept_language)
