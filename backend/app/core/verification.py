"""Rule-based verification engine. Pure Python: no web framework or database imports.

Outcomes are limited to: issue_detected, needs_confirmation, not_checked, no_issue_detected.
The engine never produces 'verified' / 'genuine' / 'bank authenticated'.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from typing import Callable, Optional

from .domain import (CaseData, ChecklistItem, DocumentData, EngineConfig, Evidence, FIELD_LABELS,
                     FieldData, Finding, OUT_CONFIRM, OUT_ISSUE, OUT_NO_ISSUE, OUT_NOT_CHECKED,
                     RULES_VERSION, USER_TRUSTED_STATUSES, VerificationResult)
from .normalize import (format_amount, normalize_identifier, normalize_name, parse_date)

CHECK_ORIGINALS = "Compare the values against the original FDR and the application form."


class _Ctx:
    def __init__(self, case: CaseData, checklist: list[ChecklistItem], cfg: EngineConfig, today: date):
        self.case, self.cfg, self.today = case, cfg, today
        self.checklist = checklist
        self.docs = {d.id: d for d in case.documents}
        self.fields = [f for f in case.fields if f.document_id in self.docs]
        self.by_name: dict[str, list[FieldData]] = defaultdict(list)
        for f in self.fields:
            self.by_name[f.field_name].append(f)

    def trusted(self, f: FieldData) -> bool:
        if f.value is None:
            return False
        if f.status in USER_TRUSTED_STATUSES:
            return True
        if f.needs_confirmation:
            return False
        return f.confidence is not None and f.confidence >= self.cfg.confidence_threshold

    def evidence(self, f: FieldData, display: Optional[str] = None) -> Evidence:
        d = self.docs.get(f.document_id)
        return Evidence(f.document_id, d.filename if d else None, d.doc_type if d else None,
                        f.page_number, f.field_name, display if display is not None else f.value,
                        f.raw_value, f.confidence, self.trusted(f))

    def doc_evidence(self, d: DocumentData) -> Evidence:
        return Evidence(d.id, d.filename, d.doc_type, None, None, None)


def _f(rule, title, outcome, severity, reason, next_check, evidence=None) -> Finding:
    return Finding(rule, title, outcome, severity, reason, next_check, evidence or [])


# ---------------------------------------------------------------- document level rules
def _missing_documents(c: _Ctx) -> list[Finding]:
    items = [i for i in c.checklist if i.required]
    if not items:
        return [_f("DOC-MISSING", "Required documents", OUT_NOT_CHECKED, "info",
                   "No required documents are configured for this case type.",
                   "Configure the checklist under Rules / Checklist.")]
    present = {d.doc_type for d in c.docs.values()}
    out = [_f("DOC-MISSING", f"Missing document: {i.label}", OUT_ISSUE, "high",
              f"The configured checklist requires '{i.label}' but no document of this type is attached.",
              f"Ask for '{i.label}' and upload it, or record why it is not needed.")
           for i in items if i.doc_type not in present]
    if not out:
        out.append(_f("DOC-MISSING", "Required documents", OUT_NO_ISSUE, "info",
                      "Every document type required by the configured checklist is attached "
                      "(this does not show the documents are genuine).", "None for this rule."))
    return out


def _duplicates(c: _Ctx) -> list[Finding]:
    groups: dict[str, list[DocumentData]] = defaultdict(list)
    for d in c.docs.values():
        if d.sha256:
            groups[d.sha256].append(d)
    dups = [g for g in groups.values() if len(g) > 1]
    if not dups:
        return [_f("DOC-DUPLICATE", "Duplicate files", OUT_NO_ISSUE, "info",
                   "No byte-identical files were found.", "None for this rule.")]
    return [_f("DOC-DUPLICATE", "Identical file uploaded more than once", OUT_CONFIRM, "low",
               "These files have identical content, so they are not independent evidence.",
               "Remove the duplicate or upload the correct separate document.",
               [c.doc_evidence(d) for d in g]) for g in dups]


def _processing(c: _Ctx) -> list[Finding]:
    out: list[Finding] = []
    failed = [d for d in c.docs.values() if d.processing_status == "failed"]
    waiting = [d for d in c.docs.values() if d.processing_status in ("pending", "processing")]
    if failed:
        out.append(_f("DOC-PROCESSING", "Text extraction failed", OUT_CONFIRM, "medium",
                      "OCR could not be completed for these documents, so their fields were not read automatically.",
                      "Retry processing or enter the fields manually from the original.",
                      [c.doc_evidence(d) for d in failed]))
    if waiting:
        out.append(_f("DOC-PROCESSING", "Documents still processing", OUT_NOT_CHECKED, "info",
                      "Some documents have not finished processing, so rules that need their fields could not run fully.",
                      "Wait for processing to finish, then rerun the analysis.",
                      [c.doc_evidence(d) for d in waiting]))
    if not out:
        out.append(_f("DOC-PROCESSING", "Document processing", OUT_NO_ISSUE, "info",
                      "All documents finished processing.", "None for this rule."))
    return out


# ---------------------------------------------------------------- field level rules
def _missing_fields(c: _Ctx) -> list[Finding]:
    out: list[Finding] = []
    checked = False
    for item in c.checklist:
        if not item.required_fields:
            continue
        for d in c.docs.values():
            if d.doc_type != item.doc_type or d.processing_status in ("pending", "processing"):
                continue
            checked = True
            have = {f.field_name for f in c.fields if f.document_id == d.id}
            miss = [x for x in item.required_fields if x not in have]
            if miss:
                labels = ", ".join(FIELD_LABELS.get(x, x) for x in miss)
                ev = [Evidence(d.id, d.filename, d.doc_type, None, x, None) for x in miss]
                out.append(_f("FIELD-MISSING", f"Required fields not found in {d.filename}", OUT_ISSUE, "medium",
                              f"No value was found for: {labels}. A missing value is not a mismatch, "
                              "but the comparison rules cannot use it.",
                              "Check the original document and enter the missing fields manually.", ev))
    if not checked:
        return [_f("FIELD-MISSING", "Required fields", OUT_NOT_CHECKED, "info",
                   "No processed document has required fields configured.", "None for this rule.")]
    if not out:
        out.append(_f("FIELD-MISSING", "Required fields", OUT_NO_ISSUE, "info",
                      "All configured required fields have a value or a flagged candidate.", "None for this rule."))
    return out


def _unconfirmed(c: _Ctx) -> list[Finding]:
    bad = [f for f in c.fields if not c.trusted(f)]
    if not bad:
        return [_f("FIELD-UNCONFIRMED", "Unreadable / unconfirmed values", OUT_NO_ISSUE, "info",
                   "Every extracted value is either confirmed by a person or read with confidence "
                   f"at or above {c.cfg.confidence_threshold:g}.", "None for this rule.")]
    by_doc: dict[int, list[FieldData]] = defaultdict(list)
    for f in bad:
        by_doc[f.document_id].append(f)
    out = []
    for did, fs in by_doc.items():
        d = c.docs[did]
        out.append(_f("FIELD-UNCONFIRMED", f"Values need confirmation in {d.filename}", OUT_CONFIRM, "medium",
                      f"{len(fs)} value(s) are unreadable, uncertain or not yet confirmed by a person. "
                      "OCR output is not trusted until confirmed.",
                      "Open the original at the page shown, then confirm or correct each value.",
                      [c.evidence(f, f.value if f.value is not None else "(no usable value)") for f in fs]))
    return out


# ---------------------------------------------------------------- comparison rules
def _outcome_for(evid_fields: list[FieldData], c: _Ctx) -> tuple[str, str]:
    if all(c.trusted(f) for f in evid_fields):
        return OUT_ISSUE, "high"
    return OUT_CONFIRM, "medium"


def _similarity_note(a: str, b: str) -> str:
    r = SequenceMatcher(None, a, b).ratio()
    return " The values are very similar, so an OCR misread is possible." if r >= 0.85 else ""


def _compare_text(c: _Ctx, name: str, rule_id: str, title: str,
                  norm: Callable[[str], str]) -> list[Finding]:
    vals = [f for f in c.by_name.get(name, []) if f.value is not None]
    if len({f.document_id for f in vals}) < 2:
        return [_f(rule_id, title, OUT_NOT_CHECKED, "info",
                   f"Fewer than two documents contain a readable '{FIELD_LABELS[name]}', so no comparison was possible.",
                   "Enter the value for each document if it should be compared.")]
    groups: dict[str, list[FieldData]] = defaultdict(list)
    for f in vals:
        groups[norm(f.value)].append(f)
    if len(groups) == 1:
        return [_f(rule_id, title, OUT_NO_ISSUE, "info",
                   f"'{FIELD_LABELS[name]}' agrees across documents after ignoring case, spacing and punctuation "
                   "(no issue detected by configured rules; this does not show the document is genuine).",
                   "None for this rule.", [c.evidence(f) for f in vals])]
    outcome, sev = _outcome_for(vals, c)
    keys = list(groups)
    note = _similarity_note(keys[0], keys[1]) if len(keys) == 2 else ""
    reason = (f"Different '{FIELD_LABELS[name]}' values appear in different documents."
              if outcome == OUT_ISSUE else
              f"Different '{FIELD_LABELS[name]}' values appear, but at least one value is unconfirmed "
              "so this may be an OCR error.") + note
    return [_f(rule_id, title, outcome, sev, reason, CHECK_ORIGINALS, [c.evidence(f) for f in vals])]


def _amount_pairs(c: _Ctx):
    pairs, no_currency = [], []
    for a in c.by_name.get("principal_amount", []):
        if a.value is None:
            continue
        try:
            amt = Decimal(a.value)
        except InvalidOperation:
            continue
        cur = next((x for x in c.by_name.get("currency", [])
                    if x.document_id == a.document_id and x.value), None)
        (pairs if cur else no_currency).append((a, cur, amt))
    return pairs, no_currency


def _compare_amounts(c: _Ctx) -> list[Finding]:
    pairs, no_cur = _amount_pairs(c)
    out: list[Finding] = []
    for a, _, amt in no_cur:
        out.append(_f("CMP-AMOUNT", "Amount cannot be compared: currency missing", OUT_CONFIRM, "medium",
                      "An amount without a currency is never compared with another amount.",
                      "Enter the currency shown on the document.", [c.evidence(a, format_amount(amt))]))
    if len({a.document_id for a, _, _ in pairs}) < 2:
        if not out:
            out.append(_f("CMP-AMOUNT", "Principal amount comparison", OUT_NOT_CHECKED, "info",
                          "Fewer than two documents contain a readable amount with a currency.",
                          "Enter the amount and currency for each document if they should be compared."))
        return out
    by_cur: dict[str, list] = defaultdict(list)
    for a, cur, amt in pairs:
        by_cur[cur.value].append((a, cur, amt))
    compared_any, conflict_any = False, False
    for cur_code, items in by_cur.items():
        if len({a.document_id for a, _, _ in items}) < 2:
            continue
        compared_any = True
        if len({amt for _, _, amt in items}) > 1:
            conflict_any = True
            fs = [x for a, cur, _ in items for x in (a, cur)]
            outcome, sev = _outcome_for(fs, c)
            ev = [c.evidence(a, f"{cur_code} {format_amount(amt)}") for a, _, amt in items]
            reason = (f"The principal amount differs between documents (same currency, {cur_code}).")
            if outcome != OUT_ISSUE:
                reason += " At least one value or currency is unconfirmed, so this may be an OCR error."
            out.append(_f("CMP-AMOUNT", "Conflicting principal amounts", outcome, sev, reason, CHECK_ORIGINALS, ev))
    if len(by_cur) > 1:
        out.append(_f("CMP-AMOUNT", "Amounts in different currencies not compared", OUT_NOT_CHECKED, "info",
                      "Amounts in different currencies are never compared with each other; see the currency finding.",
                      "Resolve the currency question first."))
    elif compared_any and not conflict_any:
        items = next(iter(by_cur.values()))
        out.append(_f("CMP-AMOUNT", "Principal amount comparison", OUT_NO_ISSUE, "info",
                      "Amounts match in the same currency (no issue detected by configured rules; this does not "
                      "show the document is genuine).", "None for this rule.",
                      [c.evidence(a, f"{cur.value} {format_amount(amt)}") for a, cur, amt in items]))
    return out


def _compare_currency(c: _Ctx) -> list[Finding]:
    return _compare_text(c, "currency", "CMP-CURRENCY", "Currency comparison", lambda s: s.strip().upper())


def _compare_institution_record(c: _Ctx) -> list[Finding]:
    if not c.case.institution_name.strip():
        return []
    vals = [f for f in c.by_name.get("beneficiary_name", []) if f.value is not None]
    if not vals:
        return []
    key = normalize_name(c.case.institution_name)
    off = [f for f in vals if normalize_name(f.value) != key]
    if not off:
        return []
    return [_f("CMP-INSTITUTION-RECORD", "Name differs from the institution entered on the case", OUT_CONFIRM, "low",
               f"The case record says '{c.case.institution_name}', which differs from the document value. "
               "The case name was typed by a user and may be informal, so this is only a prompt to check.",
               "Confirm which name is correct for this case.", [c.evidence(f) for f in off])]


# ---------------------------------------------------------------- date rules
def _date_fields(c: _Ctx, name: str):
    out = []
    for f in c.by_name.get(name, []):
        if f.value is None:
            continue
        pd = parse_date(f.value)
        out.append((f, pd))
    return out


def _compare_dates(c: _Ctx, name: str, rule_id: str, title: str) -> list[Finding]:
    items = [(f, pd) for f, pd in _date_fields(c, name) if pd.value]
    if len({f.document_id for f, _ in items}) < 2:
        return [_f(rule_id, title, OUT_NOT_CHECKED, "info",
                   f"Fewer than two documents contain a readable '{FIELD_LABELS[name]}'.",
                   "Enter the date for each document if it should be compared.")]
    if len({pd.value for _, pd in items}) == 1:
        return [_f(rule_id, title, OUT_NO_ISSUE, "info",
                   f"'{FIELD_LABELS[name]}' agrees across documents (no issue detected by configured rules).",
                   "None for this rule.", [c.evidence(f, pd.value.isoformat()) for f, pd in items])]
    trusted_all = all(c.trusted(f) and not pd.ambiguous for f, pd in items)
    return [_f(rule_id, title, OUT_ISSUE if trusted_all else OUT_CONFIRM, "high" if trusted_all else "medium",
               f"Different '{FIELD_LABELS[name]}' dates appear in different documents."
               + ("" if trusted_all else " At least one date is unconfirmed or has ambiguous day/month order."),
               CHECK_ORIGINALS, [c.evidence(f, pd.value.isoformat()) for f, pd in items])]


def _date_order(c: _Ctx) -> list[Finding]:
    issues = [(f, pd) for f, pd in _date_fields(c, "issue_date") if pd.value]
    mats = [(f, pd) for f, pd in _date_fields(c, "maturity_date") if pd.value]
    if not issues or not mats:
        return [_f("DATE-ORDER", "Date ordering", OUT_NOT_CHECKED, "info",
                   "An issue date and a maturity date are both needed to check their order.",
                   "Enter the missing date if the order should be checked.")]
    out = []
    for fi, pi in issues:
        for fm, pm in mats:
            if pi.value >= pm.value:
                ok = c.trusted(fi) and c.trusted(fm) and not pi.ambiguous and not pm.ambiguous
                out.append(_f("DATE-ORDER", "Maturity date is not after issue date",
                              OUT_ISSUE if ok else OUT_CONFIRM, "high" if ok else "medium",
                              f"The issue date {pi.value.isoformat()} is on or after the maturity date "
                              f"{pm.value.isoformat()}." + ("" if ok else " A value is unconfirmed or ambiguous."),
                              "Check both dates on the original FDR; one may be misread or mistyped.",
                              [c.evidence(fi, pi.value.isoformat()), c.evidence(fm, pm.value.isoformat())]))
    if not out:
        out.append(_f("DATE-ORDER", "Date ordering", OUT_NO_ISSUE, "info",
                      "Every maturity date is after every issue date (no issue detected by configured rules).",
                      "None for this rule."))
    return out


def _maturity(c: _Ctx) -> list[Finding]:
    if not c.case.check_maturity:
        return [_f("DATE-MATURITY", "Maturity timing", OUT_NOT_CHECKED, "info",
                   "Maturity timing is not checked for this case type.", "None for this rule.")]
    mats = [(f, pd) for f, pd in _date_fields(c, "maturity_date") if pd.value]
    if not mats:
        return [_f("DATE-MATURITY", "Maturity timing", OUT_NOT_CHECKED, "info",
                   "No readable maturity date is available.", "Enter the maturity date.")]
    out = []
    for f, pd in mats:
        ok = c.trusted(f) and not pd.ambiguous
        days = (pd.value - c.today).days
        if days < 0:
            title, reason, sev = "Maturity date has passed", f"The maturity date {pd.value.isoformat()} was {-days} day(s) before {c.today.isoformat()}.", "medium"
        elif days <= c.cfg.approaching_maturity_days:
            title, reason, sev = "Maturity date is approaching", f"The maturity date {pd.value.isoformat()} is {days} day(s) after {c.today.isoformat()}.", "low"
        else:
            continue
        out.append(_f("DATE-MATURITY", title, OUT_ISSUE if ok else OUT_CONFIRM, sev,
                      reason + ("" if ok else " The date is unconfirmed."),
                      "Check the current status of the deposit with the issuing bank through official channels.",
                      [c.evidence(f, pd.value.isoformat())]))
    if not out:
        out.append(_f("DATE-MATURITY", "Maturity timing", OUT_NO_ISSUE, "info",
                      "No maturity date is past or within the configured warning window.", "None for this rule."))
    return out


# ---------------------------------------------------------------- entry point
def run_verification(case: CaseData, checklist: list[ChecklistItem],
                     config: Optional[EngineConfig] = None, today: Optional[date] = None) -> VerificationResult:
    cfg = config or EngineConfig()
    c = _Ctx(case, checklist, cfg, today or date.today())
    findings: list[Finding] = []
    for step in (_missing_documents, _duplicates, _processing, _missing_fields, _unconfirmed,
                 lambda x: _compare_text(x, "fdr_number", "CMP-FDR-NUMBER", "FDR number comparison", normalize_identifier),
                 _compare_amounts, _compare_currency,
                 lambda x: _compare_text(x, "bank_name", "CMP-BANK", "Issuing bank comparison", normalize_name),
                 lambda x: _compare_text(x, "beneficiary_name", "CMP-BENEFICIARY", "Institution / beneficiary comparison", normalize_name),
                 _compare_institution_record,
                 lambda x: _compare_dates(x, "issue_date", "CMP-ISSUE-DATE", "Issue date comparison"),
                 lambda x: _compare_dates(x, "maturity_date", "CMP-MATURITY-DATE", "Maturity date comparison"),
                 _date_order, _maturity):
        findings.extend(step(c))
    summary = {o: sum(1 for f in findings if f.outcome == o)
               for o in (OUT_ISSUE, OUT_CONFIRM, OUT_NOT_CHECKED, OUT_NO_ISSUE)}
    if summary[OUT_ISSUE]:
        overall = OUT_ISSUE
    elif summary[OUT_CONFIRM]:
        overall = OUT_CONFIRM
    else:
        overall = OUT_NO_ISSUE
    return VerificationResult(findings, RULES_VERSION, datetime.now(timezone.utc), overall, summary)
