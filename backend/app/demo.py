"""Demo data: fictional documents pushed through the SAME upload/OCR/analysis code as real cases."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from . import services
from .config import Settings
from .core import synthetic
from .core.file_validation import validate_upload
from .core.scenarios import SYNTHETIC_TAG, build_scenarios
from .errors import ApiError


def reset_demo(db: Session, settings: Settings) -> int:
    """Deletes ONLY cases flagged is_demo. User-created cases are never touched."""
    cases = db.scalars(select(m.Case).where(m.Case.is_demo.is_(True))).all()
    for c in cases:
        services.delete_case(db, settings, c)
    services.audit(db, None, "demo_reset", {"cases_removed": len(cases)}, case_code="-")
    db.commit()
    return len(cases)


def seed_demo(db: Session, settings: Settings) -> list[dict]:
    reset_demo(db, settings)
    ok, _ = services.ocr_status(settings)
    results = []
    for scn in build_scenarios():
        ct = db.scalar(select(m.CaseType).where(m.CaseType.name == scn.case_type_name))
        if ct is None:
            raise ApiError(409, "demo_case_type_missing",
                           "The demo case type no longer exists. Restore the default checklist before seeding.")
        case = services.create_case(
            db, institution_name=scn.institution, case_type_id=ct.id, application_ref=f"DEMO-{scn.key}",
            notes=f"{SYNTHETIC_TAG} - Scenario {scn.key}: {scn.title}. {scn.description}", is_demo=True)
        db.flush()
        for d in scn.documents:
            content = synthetic.to_png_bytes(d.image)
            v = validate_upload(d.filename, "image/png", content, max_bytes=settings.max_upload_bytes,
                                max_pdf_pages=settings.max_pdf_pages)
            doc = services.store_document(db, settings, case, d.doc_type, d.filename, content, v)
            services.process_document(db, settings, doc)   # real OCR, run inline for seeding
        services.finish_processing(db, case)
        services.run_analysis(db, settings, case)
        db.commit()
        s = services.summarize(case)
        results.append({"scenario": scn.key, "title": scn.title, "case_id": case.id, "case_code": case.case_code,
                        "expected": scn.expected, "issues": s.issue_count, "needs_confirmation": s.needs_confirmation_count,
                        "overall_status": case.analysis_runs[-1].overall_status, "ocr_available": ok})
    return results
