"""Database-backed business logic. Verification and extraction rules live in app.core (no DB)."""
from __future__ import annotations

import logging
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from . import models as m
from .config import Settings
from .core import ocr
from .core.defaults import DEFAULT_CASE_TYPES, DOC_TYPE_LABELS
from .core.domain import (CaseData, ChecklistItem, DocumentData, EngineConfig, FIELD_LABELS, FieldData,
                          OUT_CONFIRM, OUT_ISSUE, RULES_VERSION, ST_CONFIRMED, ST_MANUAL)
from .core.extraction import extract_fields
from .core.file_validation import ValidatedFile
from .core.manual import ManualValueError, normalize_manual_value
from .core.verification import run_verification
from .errors import ApiError
from .schemas import (AnalysisOut, CaseDetail, CaseSummary, ChecklistStatus, DocumentOut, FieldOut, FindingOut,
                      ReportOut, StatusHistoryOut)

log = logging.getLogger("evidencelens")  # never log OCR text, field values or identifiers

DISCLAIMER = ("Decision support only. Results come from configured rules applied to OCR text and typed values. "
              "They do not authenticate an FDR, do not involve any bank or AICTE system, and are not an approval "
              "or rejection of any refund.")
LIMITATIONS = [
    "FDR EvidenceLens is a prototype decision-support tool and is not an official AICTE system.",
    "The FDR was not verified with the issuing bank and no bank, AICTE or government system was contacted.",
    "OCR output can be wrong and is never proof that a document is genuine.",
    "The checklist is a demonstration checklist, not an official list of requirements.",
    "'Review Completed' only records that the human review step in this prototype was finished; it is not an "
    "approval, rejection or release of any refund or money.",
    "The audit history is application-level logging in a local database and is not a tamper-proof regulatory audit trail.",
]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ helpers
def safe_path(upload_dir: Path, stored_filename: str) -> Path:
    root = upload_dir.resolve()
    path = (root / stored_filename).resolve()
    if path.parent != root:
        raise ApiError(400, "invalid_path", "Invalid document path.")
    return path


def audit(db: Session, case: Optional[m.Case], action: str, details: Optional[dict] = None, actor: str = "user",
          case_code: Optional[str] = None, case_id: Optional[int] = None) -> None:
    db.add(m.AuditEvent(case_id=case.id if case else case_id, case_code=case.case_code if case else case_code,
                        action=action, actor=actor, details=details or {}))


def get_case(db: Session, case_id: int) -> m.Case:
    case = db.get(m.Case, case_id)
    if case is None:
        raise ApiError(404, "not_found", "Case not found.")
    return case


def get_document(db: Session, case_id: int, doc_id: int) -> m.Document:
    """Always scoped by case so a document can never be reached through another case's URL."""
    doc = db.scalar(select(m.Document).where(m.Document.id == doc_id, m.Document.case_id == case_id))
    if doc is None:
        raise ApiError(404, "not_found", "Document not found in this case.")
    return doc


def set_status(db: Session, case: m.Case, new_status: str, actor: str, note: Optional[str] = None,
               quiet: bool = False) -> None:
    old = case.status
    if old == new_status:
        return
    case.status = new_status
    case.updated_at = utcnow()
    db.add(m.StatusHistory(case_id=case.id, from_status=old, to_status=new_status, actor=actor, note=note))
    if not quiet:
        audit(db, case, "status_changed", {"from": old, "to": new_status, "note": note}, actor=actor)


def mark_changed(db: Session, case: m.Case, reason: str) -> None:
    """Any data change makes the last analysis stale; a completed review is reopened (and logged)."""
    case.analysis_stale = True
    case.updated_at = utcnow()
    if case.status == "review_completed":
        set_status(db, case, "needs_review", "system", f"Reopened automatically: {reason}")


# ------------------------------------------------------------------ seed config
def seed_defaults(db: Session) -> None:
    if db.scalar(select(func.count()).select_from(m.CaseType)):
        return
    for ct in DEFAULT_CASE_TYPES:
        row = m.CaseType(name=ct["name"], description=ct["description"], check_maturity=ct["check_maturity"])
        for r in ct["rules"]:
            row.rules.append(m.ChecklistRule(doc_type=r["doc_type"], label=r["label"], required=r["required"],
                                             required_fields=list(r["required_fields"])))
        db.add(row)
    db.commit()


# ------------------------------------------------------------------ cases
def create_case(db: Session, *, institution_name: str, case_type_id: int, institution_ref=None, application_ref=None,
                notes=None, is_demo: bool = False) -> m.Case:
    ct = db.get(m.CaseType, case_type_id)
    if ct is None:
        raise ApiError(422, "invalid_case_type", "The selected case type does not exist.")
    case = m.Case(institution_name=institution_name, institution_ref=institution_ref, case_type_id=ct.id,
                  application_ref=application_ref, notes=notes, status="draft", is_demo=is_demo)
    db.add(case)
    db.flush()
    case.case_code = f"EL-{case.created_at.year}-{case.id:05d}"
    db.flush()
    db.add(m.StatusHistory(case_id=case.id, from_status=None, to_status="draft", actor="system", note="Case created"))
    audit(db, case, "case_created", {"case_type": ct.name, "demo": is_demo})
    return case


def summarize(case: m.Case) -> CaseSummary:
    issue_findings = [f for f in case.findings if f.outcome == OUT_ISSUE]
    return CaseSummary(
        id=case.id, case_code=case.case_code, institution_name=case.institution_name, case_type_id=case.case_type_id,
        case_type_name=case.case_type.name, application_ref=case.application_ref, status=case.status,
        is_demo=case.is_demo, document_count=len(case.documents), analysis_stale=case.analysis_stale,
        last_analysis_at=case.last_analysis_at,
        has_missing_documents=any(f.rule_id == "DOC-MISSING" for f in issue_findings),
        has_discrepancies=any(f.rule_id.startswith(("CMP-", "DATE-")) for f in issue_findings),
        issue_count=len(issue_findings),
        needs_confirmation_count=sum(1 for f in case.findings if f.outcome == OUT_CONFIRM),
        created_at=case.created_at, updated_at=case.updated_at)


def doc_out(doc: m.Document) -> DocumentOut:
    out = DocumentOut.model_validate(doc)
    out.doc_type_label = DOC_TYPE_LABELS.get(doc.doc_type, doc.doc_type)
    out.fields = [field_out(f) for f in doc.fields]
    return out


def field_out(f: m.ExtractedFieldValue) -> FieldOut:
    out = FieldOut.model_validate(f)
    out.label = FIELD_LABELS.get(f.field_name, f.field_name)
    return out


def case_detail(case: m.Case, settings: Settings) -> CaseDetail:
    ok, msg = ocr_status(settings)
    base = summarize(case).model_dump()
    return CaseDetail(**base, institution_ref=case.institution_ref, notes=case.notes,
                      reviewer_notes=case.reviewer_notes, review_outcome=case.review_outcome,
                      documents=[doc_out(d) for d in case.documents],
                      status_history=[StatusHistoryOut.model_validate(h) for h in case.status_history],
                      ocr_available=ok, ocr_message=msg)


def ocr_status(settings: Settings) -> tuple[bool, str]:
    ocr.configure(settings.tesseract_cmd or None)
    return ocr.check_ocr_available()


# ------------------------------------------------------------------ documents
def store_document(db: Session, settings: Settings, case: m.Case, doc_type: str, display_name: str,
                   content: bytes, v: ValidatedFile) -> m.Document:
    allowed = {r.doc_type for r in case.case_type.rules} | {"other"}
    if doc_type not in allowed:
        raise ApiError(422, "invalid_doc_type", f"Document type must be one of: {', '.join(sorted(allowed))}.")
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}{v.extension}"
    path = safe_path(settings.upload_dir, stored)
    path.write_bytes(content)
    doc = m.Document(case_id=case.id, doc_type=doc_type, original_filename=display_name, stored_filename=stored,
                     mime_type=v.mime, size_bytes=v.size, sha256=v.sha256, page_count=v.page_count,
                     processing_status="pending")
    db.add(doc)
    db.flush()
    audit(db, case, "document_uploaded", {"document_id": doc.id, "filename": display_name, "doc_type": doc_type,
                                          "size_bytes": v.size})
    mark_changed(db, case, "a document was uploaded")
    if case.status == "draft":
        set_status(db, case, "processing", "system", "Document processing started", quiet=True)
    return doc


def _fail(doc: m.Document, message: str) -> None:
    doc.processing_status = "failed"
    doc.processing_error = message


def process_document(db: Session, settings: Settings, doc: m.Document) -> None:
    """Run OCR + extraction. Never raises: failures are recorded on the document."""
    doc.processing_status, doc.processing_error = "processing", None
    db.flush()
    try:
        ocr.configure(settings.tesseract_cmd or None)
        pages = ocr.ocr_file(str(safe_path(settings.upload_dir, doc.stored_filename)), doc.mime_type,
                             settings.max_pdf_pages, settings.ocr_lang)
        extracted = extract_fields(pages, settings.ocr_confidence_threshold)
    except ocr.OcrUnavailableError as exc:
        _fail(doc, f"{exc} You can still enter the fields manually.")
        return
    except ocr.OcrError as exc:
        _fail(doc, f"{exc} You can retry, or enter the fields manually.")
        return
    except Exception:  # defensive: never crash the app or corrupt the case
        log.error("Unexpected OCR failure for document id=%s", doc.id)
        _fail(doc, "Unexpected processing error. You can retry, or enter the fields manually.")
        return

    doc.pages.clear()
    for f in list(doc.fields):
        if f.status in ("extracted", "unreadable"):   # keep manual / confirmed values
            doc.fields.remove(f)
    db.flush()
    for p in pages:
        doc.pages.append(m.DocumentPage(page_number=p.page_number, text=p.text, mean_confidence=p.mean_confidence))
    kept = {f.field_name for f in doc.fields}
    for e in extracted:
        if e.field_name in kept:
            continue
        doc.fields.append(m.ExtractedFieldValue(
            case_id=doc.case_id, field_name=e.field_name, value=e.value, raw_value=e.raw_value,
            page_number=e.page_number, confidence=e.confidence, status=e.status,
            needs_confirmation=e.needs_confirmation, note=e.note))
    doc.processing_status = "processed"


def finish_processing(db: Session, case: m.Case) -> None:
    pending = any(d.processing_status in ("pending", "processing") for d in case.documents)
    if not pending and case.status == "processing":
        set_status(db, case, "draft", "system", "Document processing finished", quiet=True)


def process_document_job(session_factory, settings: Settings, doc_id: int) -> None:
    """Background task entry point (own DB session)."""
    with session_factory() as db:
        try:
            doc = db.get(m.Document, doc_id)
            if doc is None:
                return
            process_document(db, settings, doc)
            finish_processing(db, doc.case)
            db.commit()
        except Exception:
            db.rollback()
            log.error("Processing job failed for document id=%s", doc_id)
            with session_factory() as db2:
                d = db2.get(m.Document, doc_id)
                if d is not None:
                    _fail(d, "Unexpected processing error. You can retry, or enter the fields manually.")
                    finish_processing(db2, d.case)
                    db2.commit()


def delete_document(db: Session, settings: Settings, doc: m.Document) -> None:
    case = doc.case
    info = {"document_id": doc.id, "filename": doc.original_filename, "doc_type": doc.doc_type}
    try:
        safe_path(settings.upload_dir, doc.stored_filename).unlink(missing_ok=True)
    except OSError:
        log.error("Could not remove stored file for document id=%s", doc.id)
    db.delete(doc)   # cascades to this document's pages and fields only
    db.flush()
    audit(db, case, "document_deleted", info)
    mark_changed(db, case, "a document was removed")


# ------------------------------------------------------------------ fields
def update_field(db: Session, doc: m.Document, field_name: str, value: Optional[str], confirm: bool) -> m.ExtractedFieldValue:
    if field_name not in FIELD_LABELS:
        raise ApiError(404, "not_found", f"Unknown field '{field_name}'.")
    existing = next((f for f in doc.fields if f.field_name == field_name), None)
    case = doc.case
    if value is not None and value.strip():
        try:
            norm, raw, embedded_currency = normalize_manual_value(field_name, value)
        except ManualValueError as exc:
            raise ApiError(422, "invalid_field_value", str(exc)) from exc
        before = existing.value if existing else None
        if existing is None:
            existing = m.ExtractedFieldValue(case_id=doc.case_id, field_name=field_name)
            doc.fields.append(existing)
        existing.value, existing.raw_value = norm, raw
        existing.status, existing.needs_confirmation, existing.confidence, existing.note = ST_MANUAL, False, None, None
        existing.updated_at = utcnow()
        if embedded_currency and not any(f.field_name == "currency" for f in doc.fields):
            doc.fields.append(m.ExtractedFieldValue(case_id=doc.case_id, field_name="currency", value=embedded_currency,
                                                    raw_value=embedded_currency, status=ST_MANUAL,
                                                    needs_confirmation=False,
                                                    page_number=existing.page_number))
        audit(db, case, "field_corrected", {"document_id": doc.id, "field": field_name, "previous": before, "new": norm})
    elif confirm:
        if existing is None or existing.value is None:
            raise ApiError(422, "nothing_to_confirm", "There is no readable value to confirm. Enter the value instead.")
        existing.status, existing.needs_confirmation, existing.note = ST_CONFIRMED, False, None
        existing.updated_at = utcnow()
        audit(db, case, "field_confirmed", {"document_id": doc.id, "field": field_name})
    else:
        raise ApiError(422, "invalid_request", "Provide a value to save, or set confirm=true to confirm the extracted value.")
    db.flush()
    mark_changed(db, case, "a field was edited")
    return existing


# ------------------------------------------------------------------ analysis
def checklist_items(case: m.Case) -> list[ChecklistItem]:
    return [ChecklistItem(r.doc_type, r.label, r.required, list(r.required_fields or [])) for r in case.case_type.rules]


def build_case_data(case: m.Case) -> CaseData:
    docs = [DocumentData(d.id, d.original_filename, d.doc_type, d.processing_status, d.sha256) for d in case.documents]
    fields = [FieldData(f.document_id, f.field_name, f.value, f.raw_value, f.page_number, f.confidence, f.status,
                        f.needs_confirmation, f.note) for d in case.documents for f in d.fields]
    return CaseData(case.case_type.name, case.institution_name, case.case_type.check_maturity, docs, fields)


def run_analysis(db: Session, settings: Settings, case: m.Case) -> m.AnalysisRun:
    result = run_verification(build_case_data(case), checklist_items(case),
                              EngineConfig(settings.ocr_confidence_threshold, settings.approaching_maturity_days))
    case.findings.clear()
    db.flush()
    run = m.AnalysisRun(case_id=case.id, run_at=result.generated_at, rules_version=result.rules_version,
                        overall_status=result.overall_status, summary=result.summary)
    db.add(run)
    db.flush()
    for f in result.findings:
        case.findings.append(m.Finding(analysis_run_id=run.id, rule_id=f.rule_id, title=f.title, outcome=f.outcome,
                                       severity=f.severity, reason=f.reason, next_check=f.next_check,
                                       evidence=[asdict(e) for e in f.evidence]))
    case.last_analysis_at, case.analysis_stale, case.updated_at = result.generated_at, False, utcnow()
    audit(db, case, "analysis_run", {"rules_version": result.rules_version, "overall": result.overall_status,
                                     "summary": result.summary})
    if case.status in ("draft", "processing"):
        set_status(db, case, "needs_review", "system", "Analysis completed; human review is required")
    return run


def checklist_status(case: m.Case) -> list[ChecklistStatus]:
    out = []
    for r in case.case_type.rules:
        ids = [d.id for d in case.documents if d.doc_type == r.doc_type]
        out.append(ChecklistStatus(doc_type=r.doc_type, label=r.label, required=r.required, present=bool(ids),
                                   document_ids=ids))
    return out


def fields_needing_confirmation(case: m.Case, threshold: float) -> list[dict[str, Any]]:
    out = []
    for d in case.documents:
        for f in d.fields:
            trusted = f.value is not None and (f.status in (ST_CONFIRMED, ST_MANUAL) or (
                not f.needs_confirmation and f.confidence is not None and f.confidence >= threshold))
            if not trusted:
                out.append({"document_id": d.id, "filename": d.original_filename, "field_name": f.field_name,
                            "label": FIELD_LABELS.get(f.field_name, f.field_name), "value": f.value,
                            "page": f.page_number, "confidence": f.confidence, "status": f.status, "note": f.note})
    return out


def analysis_out(case: m.Case, settings: Settings) -> AnalysisOut:
    run = case.analysis_runs[-1] if case.analysis_runs else None
    return AnalysisOut(
        has_run=run is not None, stale=case.analysis_stale, last_analysis_at=case.last_analysis_at,
        rules_version=run.rules_version if run else None, overall_status=run.overall_status if run else None,
        summary=run.summary if run else {}, checklist=checklist_status(case),
        findings=[FindingOut.model_validate(f) for f in case.findings],
        fields_needing_confirmation=fields_needing_confirmation(case, settings.ocr_confidence_threshold),
        disclaimer=DISCLAIMER)


# ------------------------------------------------------------------ review
def change_status(db: Session, case: m.Case, status: str, note: Optional[str], confirm: bool) -> None:
    if not confirm:
        raise ApiError(400, "confirmation_required", "This action must be explicitly confirmed (confirm=true).")
    if status == "review_completed":
        if not case.last_analysis_at:
            raise ApiError(409, "analysis_required", "Run the analysis before completing the review.")
        if case.analysis_stale:
            raise ApiError(409, "analysis_stale", "Data changed since the last analysis. Rerun the analysis first.")
        if not note or len(note.strip()) < 3:
            raise ApiError(422, "outcome_required", "Record a short review outcome note before completing the review.")
        case.review_outcome = note.strip()
    set_status(db, case, status, "reviewer", note.strip() if note else None)


# ------------------------------------------------------------------ report
def build_report(case: m.Case, settings: Settings) -> ReportOut:
    a = analysis_out(case, settings)
    fields = []
    for d in case.documents:
        for f in d.fields:
            confirmed = f.status in (ST_CONFIRMED, ST_MANUAL)
            fields.append({"document": d.original_filename, "document_id": d.id,
                           "field": FIELD_LABELS.get(f.field_name, f.field_name), "value": f.value,
                           "page": f.page_number, "confidence": f.confidence,
                           "confirmation": ("Confirmed by reviewer" if f.status == ST_CONFIRMED else
                                            "Entered/corrected by reviewer" if f.status == ST_MANUAL else
                                            "Unreadable - needs confirmation" if f.value is None else
                                            "OCR value - needs confirmation" if f.needs_confirmation or
                                            (f.confidence or 0) < settings.ocr_confidence_threshold else
                                            "OCR value - high confidence, not reviewed"),
                           "confirmed": confirmed})
    nexts = list(dict.fromkeys(f.next_check for f in a.findings
                               if f.outcome in (OUT_ISSUE, OUT_CONFIRM) and f.next_check))
    docs = [{"id": d.id, "filename": d.original_filename, "type": DOC_TYPE_LABELS.get(d.doc_type, d.doc_type),
             "uploaded_at": d.uploaded_at, "processing_status": d.processing_status, "pages": d.page_count,
             "sha256_prefix": d.sha256[:12]} for d in case.documents]
    return ReportOut(
        case_code=case.case_code, institution_name=case.institution_name, institution_ref=case.institution_ref,
        application_ref=case.application_ref, case_type_name=case.case_type.name, status=case.status,
        generated_at=utcnow(), last_analysis_at=case.last_analysis_at, analysis_stale=case.analysis_stale,
        rules_version=a.rules_version, is_demo=case.is_demo, documents=docs, fields=fields, checklist=a.checklist,
        findings=a.findings, next_checks=nexts, reviewer_notes=case.reviewer_notes, review_outcome=case.review_outcome,
        status_history=[StatusHistoryOut.model_validate(h) for h in case.status_history], limitations=LIMITATIONS)


# ------------------------------------------------------------------ listing / dashboard
def list_cases(db: Session, q: Optional[str], status: Optional[str], page: int, page_size: int):
    stmt = select(m.Case)
    if status:
        stmt = stmt.where(m.Case.status == status)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(m.Case.case_code.ilike(like), m.Case.institution_name.ilike(like),
                              m.Case.application_ref.ilike(like), m.Case.institution_ref.ilike(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(m.Case.updated_at.desc(), m.Case.id.desc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return [summarize(c) for c in rows], total


def dashboard(db: Session) -> dict:
    total = db.scalar(select(func.count()).select_from(m.Case)) or 0
    by_status = dict(db.execute(select(m.Case.status, func.count()).group_by(m.Case.status)).all())
    missing = db.scalar(select(func.count(func.distinct(m.Finding.case_id))).where(
        m.Finding.rule_id == "DOC-MISSING", m.Finding.outcome == OUT_ISSUE)) or 0
    disc = db.scalar(select(func.count(func.distinct(m.Finding.case_id))).where(
        m.Finding.outcome == OUT_ISSUE, or_(m.Finding.rule_id.like("CMP-%"), m.Finding.rule_id.like("DATE-%")))) or 0
    recent = db.scalars(select(m.Case).order_by(m.Case.updated_at.desc(), m.Case.id.desc()).limit(8)).all()
    return {"total_cases": total, "needs_review": by_status.get("needs_review", 0), "missing_documents": missing,
            "unresolved_discrepancies": disc, "by_status": by_status, "recent_cases": [summarize(c) for c in recent]}


def delete_case(db: Session, settings: Settings, case: m.Case) -> None:
    for d in list(case.documents):
        try:
            safe_path(settings.upload_dir, d.stored_filename).unlink(missing_ok=True)
        except OSError:
            log.error("Could not remove stored file for document id=%s", d.id)
    audit(db, case, "case_deleted", {"institution": case.institution_name, "documents": len(case.documents)})
    db.flush()
    db.delete(case)
