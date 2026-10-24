"""Validation/normalisation of values typed by a person (pure Python)."""
from __future__ import annotations

import re
from typing import Optional

from .domain import DATE_FIELDS, FIELD_LABELS
from .normalize import collapse_ws, parse_amount, parse_currency, parse_date


class ManualValueError(ValueError):
    pass


def normalize_manual_value(field_name: str, value: str) -> tuple[str, str, Optional[str]]:
    """Return (normalised_value, raw_value, currency_embedded_in_amount_or_None)."""
    if field_name not in FIELD_LABELS:
        raise ManualValueError(f"Unknown field '{field_name}'.")
    raw = collapse_ws(value)
    if not raw:
        raise ManualValueError("A value is required.")
    if len(raw) > 300:
        raise ManualValueError("The value is too long.")
    if field_name == "principal_amount":
        amt, cur = parse_amount(raw)
        if amt is None:
            raise ManualValueError("Enter a positive amount such as 1,000,000.00 (a currency such as INR may be included).")
        return f"{amt}", raw, cur
    if field_name == "currency":
        cur = parse_currency(raw)
        if cur is None:
            raise ManualValueError("Enter a 3-letter currency code such as INR.")
        return cur, raw, None
    if field_name in DATE_FIELDS:
        pd = parse_date(raw)
        if pd.value is None:
            raise ManualValueError("Enter a valid date as YYYY-MM-DD (for example 2025-03-15).")
        if pd.ambiguous:
            raise ManualValueError("That day/month order is ambiguous. Enter the date as YYYY-MM-DD.")
        return pd.value.isoformat(), raw, None
    if field_name == "fdr_number":
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9\-/ ]{3,29}", raw):
            raise ManualValueError("An FDR number is 4-30 letters, digits, spaces, hyphens or slashes.")
    return raw, raw, None
