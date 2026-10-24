"""Deterministic, label-based field extraction from OCR pages.

Principles: only read values that follow a recognised label; never guess; if a field appears with
conflicting values on one document, or cannot be parsed cleanly, return value=None and flag it
for manual confirmation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .domain import (ExtractedField, OcrPage, ST_EXTRACTED, ST_UNREADABLE)
from .normalize import (collapse_ws, format_amount, normalize_identifier, normalize_name,
                        parse_amount, parse_currency, parse_date)

_SEP = r"\s*[:;|\-–]?\s*"

_LABELS: dict[str, list[str]] = {
    "fdr_number": [r"FDR\s*(?:No|Number|Num)\b\.?", r"Deposit\s+Receipt\s*(?:No|Number)\b\.?",
                   r"Receipt\s*(?:No|Number|Num)\b\.?"],
    "bank_name": [r"Issuing\s+Bank\b", r"Bank\s+Name\b", r"Name\s+of\s+(?:the\s+)?Bank\b"],
    "branch": [r"Branch(?:\s+Name)?\b"],
    "principal_amount": [r"Principal\s+Amount\b", r"Deposit\s+Amount\b", r"FDR\s+Amount\b",
                         r"Amount\s+of\s+Deposit\b", r"Amount\s+Deposited\b"],
    "currency": [r"Currency\b"],
    "issue_date": [r"Date\s+of\s+(?:Issue|Deposit)\b", r"Issue\s+Date\b", r"Deposit\s+Date\b",
                   r"Start\s+Date\b"],
    "maturity_date": [r"Date\s+of\s+Maturity\b", r"Maturity\s+Date\b", r"Due\s+Date\b"],
    "beneficiary_name": [r"Beneficiary(?:\s+Name)?\b", r"Name\s+of\s+(?:the\s+)?(?:Depositor|Institution|Beneficiary)\b",
                         r"Depositor(?:\s+Name)?\b", r"Institution\s+Name\b", r"Payee\b",
                         r"In\s+favou?r\s+of\b"],
    "reference_number": [r"Application\s+(?:Reference\s+)?(?:No|Number|Ref)\b\.?",
                         r"Reference\s*(?:No|Number)\b\.?", r"Ref\.?\s*No\b\.?"],
    "status_reference": [r"(?:FDR\s+|Receipt\s+)?Status\b"],
}
_COMPILED = {f: [re.compile(r"^\s*(?:%s)%s(?P<v>.*?)\s*$" % (alt, _SEP), re.I) for alt in alts]
             for f, alts in _LABELS.items()}


@dataclass
class _Cand:
    field: str
    raw: str
    page: int
    conf: Optional[float]
    inferred: bool = False


def _scan(pages: list[OcrPage]) -> list[_Cand]:
    cands: list[_Cand] = []
    for page in pages:
        lines = page.lines or []
        if not lines:  # text only (no per-line confidence)
            from .domain import OcrLine
            lines = [OcrLine(t, None) for t in page.text.splitlines()]
        for line in lines:
            for fname, regs in _COMPILED.items():
                m = next((r.match(line.text) for r in regs if r.match(line.text)), None)
                if m:
                    cands.append(_Cand(fname, collapse_ws(m.group("v")), page.page_number, line.confidence))
                    break
    return cands


def _bank_fallback(pages: list[OcrPage]) -> Optional[_Cand]:
    for page in pages:
        for line in page.lines:
            t = collapse_ws(line.text)
            if re.search(r"\bbank\b", t, re.I) and 2 <= len(t.split()) <= 8 and ":" not in t \
                    and not any(r.match(t) for regs in _COMPILED.values() for r in regs):
                return _Cand("bank_name", t, page.page_number, line.confidence, inferred=True)
    return None


def _low(conf: Optional[float], threshold: float) -> bool:
    return conf is None or conf < threshold


def extract_fields(pages: list[OcrPage], confidence_threshold: float = 80.0) -> list[ExtractedField]:
    cands = _scan(pages)
    if not any(c.field == "bank_name" for c in cands):
        fb = _bank_fallback(pages)
        if fb:
            cands.append(fb)

    out: list[ExtractedField] = []
    by_field: dict[str, list[_Cand]] = {}
    for c in cands:
        by_field.setdefault(c.field, []).append(c)

    amount_currency: Optional[str] = None

    for fname, group in by_field.items():
        parsed: list[tuple[str, Optional[str], _Cand]] = []  # (key, display value, cand)
        unreadable_cands: list[_Cand] = []
        for c in group:
            if not c.raw:
                unreadable_cands.append(c)
                continue
            if fname == "principal_amount":
                amt, cur = parse_amount(c.raw)
                if amt is None:
                    unreadable_cands.append(c)
                    continue
                parsed.append((f"{amt}|{cur}", f"{amt}", c))
                amount_currency = cur
            elif fname == "currency":
                cur = parse_currency(c.raw)
                if cur is None:
                    unreadable_cands.append(c)
                    continue
                parsed.append((cur, cur, c))
            elif fname in ("issue_date", "maturity_date"):
                pd = parse_date(c.raw)
                if pd.value is None:
                    unreadable_cands.append(c)
                    continue
                parsed.append((pd.value.isoformat(), pd.value.isoformat() if not pd.ambiguous else c.raw, c))
            elif fname == "fdr_number":
                if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9\-/ ]{3,29}", c.raw):
                    unreadable_cands.append(c)
                    continue
                parsed.append((normalize_identifier(c.raw), c.raw, c))
            elif fname in ("bank_name", "beneficiary_name", "branch"):
                parsed.append((normalize_name(c.raw), c.raw, c))
            else:
                parsed.append((c.raw.casefold(), c.raw, c))

        distinct = {k for k, _, _ in parsed}
        if len(distinct) > 1:
            shown = " | ".join(dict.fromkeys(v or "" for _, v, _ in parsed))
            first = parsed[0][2]
            out.append(ExtractedField(fname, None, None, first.page, None, ST_UNREADABLE, True,
                                      f"Several different values were found on this document: {shown}. Choose the correct one."))
            continue
        if parsed:
            key, display, c = parsed[0]
            raw = c.raw
            value = display
            needs = _low(c.conf, confidence_threshold)
            note = None
            if c.inferred:
                needs, note = True, "Inferred from a header line without a label; please confirm."
            if fname in ("issue_date", "maturity_date") and parse_date(raw).ambiguous:
                needs = True
                value = raw
                note = "Day/month order is ambiguous (e.g. 05/06/2025); please enter the date as YYYY-MM-DD."
            if fname == "principal_amount":
                note = None
            out.append(ExtractedField(fname, value, raw, c.page, c.conf, ST_EXTRACTED, needs, note))
        elif unreadable_cands:
            c = unreadable_cands[0]
            out.append(ExtractedField(fname, None, c.raw or None, c.page, c.conf, ST_UNREADABLE, True,
                                      "The label was found but the value could not be read reliably."))

    # Derive currency from the amount line when there is no explicit Currency line
    amt_field = next((f for f in out if f.field_name == "principal_amount" and f.value), None)
    if amt_field and amount_currency:
        existing = next((f for f in out if f.field_name == "currency"), None)
        if existing is None:
            out.append(ExtractedField("currency", amount_currency, amount_currency, amt_field.page_number,
                                      amt_field.confidence, ST_EXTRACTED,
                                      amt_field.needs_confirmation, None))
        elif existing.value and existing.value != amount_currency:
            existing.value = None
            existing.status = ST_UNREADABLE
            existing.needs_confirmation = True
            existing.note = "The Currency line and the amount line show different currencies; please confirm."
    return out
