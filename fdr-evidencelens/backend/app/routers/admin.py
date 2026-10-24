from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .. import demo, models as m, services
from ..config import Settings
from ..core.defaults import DOC_TYPE_LABELS
from ..core.domain import FIELD_LABELS, RULES_VERSION
from ..core.file_validation import SUPPORTED_DESCRIPTION
from ..deps import get_db, get_settings_dep
from ..errors import ApiError
from ..schemas import AuditEventOut, CaseTypeOut, CaseTypeUpdate, DashboardOut, Page, RuleOut, RuleUpdate

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", summary="Health check")
def health(settings: Settings = Depends(get_settings_dep)):
    ok, msg = services.ocr_status(settings)
    return {"status": "ok", "environment": settings.app_env, "ocr_available": ok, "ocr_message": msg,
            "demo_endpoints_enabled": settings.demo_allowed, "rules_version": RULES_VERSION}


@router.get("/config", summary="Limits and labels used by the UI")
def config(settings: Settings = Depends(get_settings_dep)):
    return {"max_upload_mb": settings.max_upload_mb, "max_pdf_pages": settings.max_pdf_pages,
            "supported_formats": SUPPORTED_DESCRIPTION, "ocr_confidence_threshold": settings.ocr_confidence_threshold,
            "approaching_maturity_days": settings.approaching_maturity_days, "rules_version": RULES_VERSION,
            "doc_type_labels": DOC_TYPE_LABELS, "field_labels": FIELD_LABELS, "environment": settings.app_env,
            "demo_endpoints_enabled": settings.demo_allowed,
            "notice": "Local demo with a basic username/password login (no roles, no MFA, no password reset). Not production-ready and not an official AICTE system."}


@router.get("/dashboard", response_model=DashboardOut, summary="Dashboard metrics from stored cases")
def dashboard(db: Session = Depends(get_db)):
    return services.dashboard(db)


@router.get("/case-types", response_model=list[CaseTypeOut], summary="Case types with their checklist rules")
def case_types(db: Session = Depends(get_db)):
    return db.scalars(select(m.CaseType).order_by(m.CaseType.id)).all()


@router.patch("/case-types/{case_type_id}", response_model=CaseTypeOut, summary="Update case-type settings")
def update_case_type(case_type_id: int, body: CaseTypeUpdate, db: Session = Depends(get_db)):
    ct = db.get(m.CaseType, case_type_id)
    if ct is None:
        raise ApiError(404, "not_found", "Case type not found.")
    if body.check_maturity is not None and body.check_maturity != ct.check_maturity:
        ct.check_maturity = body.check_maturity
        db.execute(update(m.Case).where(m.Case.case_type_id == ct.id).values(analysis_stale=True))
        services.audit(db, None, "case_type_updated", {"case_type": ct.name, "check_maturity": ct.check_maturity},
                       case_code="-")
    db.commit()
    return ct


@router.put("/checklist-rules/{rule_id}", response_model=RuleOut, summary="Edit a checklist rule")
def update_rule(rule_id: int, body: RuleUpdate, db: Session = Depends(get_db)):
    rule = db.get(m.ChecklistRule, rule_id)
    if rule is None:
        raise ApiError(404, "not_found", "Checklist rule not found.")
    if body.required_fields is not None:
        bad = [f for f in body.required_fields if f not in FIELD_LABELS]
        if bad:
            raise ApiError(422, "invalid_field", f"Unknown field name(s): {', '.join(bad)}.")
        rule.required_fields = list(dict.fromkeys(body.required_fields))
    if body.label is not None:
        rule.label = " ".join(body.label.split())
    if body.required is not None:
        rule.required = body.required
    db.execute(update(m.Case).where(m.Case.case_type_id == rule.case_type_id).values(analysis_stale=True))
    services.audit(db, None, "checklist_rule_updated",
                   {"case_type": rule.case_type.name, "doc_type": rule.doc_type, "required": rule.required,
                    "required_fields": rule.required_fields}, case_code="-")
    db.commit()
    return rule


@router.get("/audit", response_model=Page[AuditEventOut], summary="Audit history across cases")
def audit_history(case_id: Optional[int] = None, action: Optional[str] = Query(None, max_length=60),
                  page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    stmt = select(m.AuditEvent)
    if case_id is not None:
        stmt = stmt.where(m.AuditEvent.case_id == case_id)
    if action:
        stmt = stmt.where(m.AuditEvent.action == action)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(m.AuditEvent.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return Page[AuditEventOut](items=[AuditEventOut.model_validate(r) for r in rows], total=total, page=page,
                               page_size=page_size)


def _require_demo(settings: Settings) -> None:
    if not settings.demo_allowed:
        raise ApiError(403, "demo_disabled",
                       "Demo seeding and reset are only available when APP_ENV=development and "
                       "ENABLE_DEMO_ENDPOINTS=true.")


@router.post("/demo/seed", summary="Load the four fictional demo cases (development only)")
def seed(db: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)):
    _require_demo(settings)
    return {"cases": demo.seed_demo(db, settings)}


@router.post("/demo/reset", summary="Delete ONLY demo cases (development only)")
def reset(db: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)):
    _require_demo(settings)
    return {"removed": demo.reset_demo(db, settings)}
