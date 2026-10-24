from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from .. import services
from ..config import Settings
from ..deps import get_db, get_settings_dep
from ..errors import ApiError
from ..schemas import (AnalysisOut, AuditEventOut, CaseCreate, CaseDetail, CaseSummary, CaseUpdate, Page, ReportOut,
                       StatusChange)

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.post("", response_model=CaseDetail, status_code=201, summary="Create a case")
def create_case(body: CaseCreate, db: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)):
    case = services.create_case(db, **body.model_dump())
    db.commit()
    return services.case_detail(case, settings)


@router.get("", response_model=Page[CaseSummary], summary="List cases (paginated, searchable)")
def list_cases(q: Optional[str] = Query(None, max_length=100),
               status: Optional[str] = Query(None, pattern="^(draft|processing|needs_review|awaiting_information|review_completed)$"),
               page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    items, total = services.list_cases(db, q, status, page, page_size)
    return Page[CaseSummary](items=items, total=total, page=page, page_size=page_size)


@router.get("/{case_id}", response_model=CaseDetail, summary="Case detail")
def get_case(case_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)):
    return services.case_detail(services.get_case(db, case_id), settings)


@router.patch("/{case_id}", response_model=CaseDetail, summary="Update case details or reviewer notes")
def update_case(case_id: int, body: CaseUpdate, db: Session = Depends(get_db),
                settings: Settings = Depends(get_settings_dep)):
    case = services.get_case(db, case_id)
    data = body.model_dump(exclude_unset=True)
    changed = []
    for key, val in data.items():
        if isinstance(val, str):
            val = val.strip() or None
        if key == "institution_name" and not val:
            raise ApiError(422, "validation_error", "Institution name cannot be empty.")
        if getattr(case, key) != val:
            setattr(case, key, val)
            changed.append(key)
    if changed:
        if "reviewer_notes" in changed:
            services.audit(db, case, "reviewer_notes_updated", {"length": len(case.reviewer_notes or "")})
        other = [k for k in changed if k != "reviewer_notes"]
        if other:
            services.audit(db, case, "case_updated", {"fields": other})
        if "institution_name" in changed:
            services.mark_changed(db, case, "the institution name changed")
        case.updated_at = services.utcnow()
    db.commit()
    return services.case_detail(case, settings)


@router.delete("/{case_id}", status_code=204, summary="Delete a case (requires confirm=true)")
def delete_case(case_id: int, confirm: bool = Query(False), db: Session = Depends(get_db),
                settings: Settings = Depends(get_settings_dep)):
    if not confirm:
        raise ApiError(400, "confirmation_required", "Deleting a case must be confirmed (confirm=true).")
    services.delete_case(db, settings, services.get_case(db, case_id))
    db.commit()


@router.post("/{case_id}/status", response_model=CaseDetail, summary="Human status change (explicit confirmation required)")
def change_status(case_id: int, body: StatusChange, db: Session = Depends(get_db),
                  settings: Settings = Depends(get_settings_dep)):
    case = services.get_case(db, case_id)
    services.change_status(db, case, body.status, body.note, body.confirm)
    db.commit()
    return services.case_detail(case, settings)


@router.post("/{case_id}/analysis", response_model=AnalysisOut, summary="Run (or rerun) the verification analysis")
def run_analysis(case_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)):
    case = services.get_case(db, case_id)
    if any(d.processing_status in ("pending", "processing") for d in case.documents):
        raise ApiError(409, "documents_processing", "Some documents are still being processed. Try again in a moment.")
    services.run_analysis(db, settings, case)
    db.commit()
    return services.analysis_out(case, settings)


@router.get("/{case_id}/analysis", response_model=AnalysisOut, summary="Latest analysis results")
def get_analysis(case_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)):
    return services.analysis_out(services.get_case(db, case_id), settings)


@router.get("/{case_id}/report", response_model=ReportOut, summary="Data for the printable case report")
def get_report(case_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)):
    return services.build_report(services.get_case(db, case_id), settings)


@router.get("/{case_id}/audit", response_model=Page[AuditEventOut], summary="Audit history for one case")
def case_audit(case_id: int, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
               db: Session = Depends(get_db)):
    services.get_case(db, case_id)
    where = m.AuditEvent.case_id == case_id
    total = db.scalar(select(func.count()).select_from(m.AuditEvent).where(where)) or 0
    rows = db.scalars(select(m.AuditEvent).where(where).order_by(m.AuditEvent.id.desc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return Page[AuditEventOut](items=[AuditEventOut.model_validate(r) for r in rows], total=total, page=page,
                               page_size=page_size)
