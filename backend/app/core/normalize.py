"""Deterministic normalisation and parsing helpers."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

_NAME_NOISE = {"LTD", "LIMITED", "PVT", "PRIVATE", "THE", "CO", "COMPANY"}


def collapse_ws(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def normalize_identifier(s: str) -> str:
    """Upper-case and drop spaces/hyphens/slashes/dots so 'fdr-123 456' == 'FDR123456'."""
    s = unicodedata.normalize("NFKC", s or "").upper()
    return re.sub(r"[\s\-_/\\.]", "", s)


def normalize_name(s: str) -> str:
    """Case/punctuation-insensitive name key; ignores LTD/LIMITED/THE style noise words."""
    t = unicodedata.normalize("NFKC", s or "").upper().replace("&", " AND ")
    t = re.sub(r"[^\w\s]", " ", t)
    tokens = t.split()
    kept = [x for x in tokens if x not in _NAME_NOISE]
    return " ".join(kept or tokens)


_CURRENCY_MAP = {"INR": "INR", "RS": "INR", "₹": "INR", "USD": "USD", "US$": "USD", "$": "USD",
                 "EUR": "EUR", "€": "EUR", "GBP": "GBP", "£": "GBP"}
_CUR_RE = re.compile(r"(?i)(INR|USD|EUR|GBP|US\$|Rs\.?|₹|\$|€|£)")


def parse_currency(text: str) -> Optional[str]:
    t = collapse_ws(text)
    m = _CUR_RE.search(t)
    if m:
        return _CURRENCY_MAP.get(m.group(1).upper().rstrip("."))
    if re.fullmatch(r"[A-Za-z]{3}", t):
        return t.upper()
    return None


def parse_amount(text: str) -> tuple[Optional[Decimal], Optional[str]]:
    """Return (amount, currency). Amount is None unless the *whole* string is a clean number
    (so an OCR-damaged '1O0,000' is never silently read as '1')."""
    t = collapse_ws(text)
    currency = parse_currency(t) if _CUR_RE.search(t) else None
    rest = _CUR_RE.sub("", t)
    rest = re.sub(r"/-|\bonly\b", "", rest, flags=re.I).strip()
    if not re.fullmatch(r"\d{1,3}(?:,\d{2,3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?", rest):
        return None, currency
    try:
        amount = Decimal(rest.replace(",", "")).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None, currency
    return (amount if amount > 0 else None), currency


def format_amount(amount: Decimal) -> str:
    return f"{amount:,.2f}"


_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


@dataclass
class ParsedDate:
    value: Optional[date]
    ambiguous: bool = False  # numeric day/month order could be read two ways


def _mk(y: int, m: int, d: int) -> Optional[date]:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def parse_date(text: Optional[str]) -> ParsedDate:
    t = collapse_ws(text)
    if not t:
        return ParsedDate(None)
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        return ParsedDate(_mk(int(m[1]), int(m[2]), int(m[3])))
    m = re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", t)
    if m:
        a, b, y = int(m[1]), int(m[2]), int(m[3])
        if a > 12:
            return ParsedDate(_mk(y, b, a))          # DD/MM
        if b > 12:
            return ParsedDate(_mk(y, a, b))          # MM/DD
        return ParsedDate(_mk(y, b, a), ambiguous=(a != b))  # assumed DD/MM, flagged
    m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?[\s\-/]+([A-Za-z]{3,9})\.?,?[\s\-/]+(\d{4})", t)
    if m and m[2][:3].lower() in _MONTHS:
        return ParsedDate(_mk(int(m[3]), _MONTHS[m[2][:3].lower()], int(m[1])))
    m = re.fullmatch(r"([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", t)
    if m and m[1][:3].lower() in _MONTHS:
        return ParsedDate(_mk(int(m[3]), _MONTHS[m[1][:3].lower()], int(m[2])))
    return ParsedDate(None)
