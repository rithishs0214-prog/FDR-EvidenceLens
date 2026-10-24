from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import services
from ..config import Settings
from ..core.file_validation import FileValidationError, sanitise_display_filename, validate_upload
from ..deps import get_db, get_settings_dep
from ..errors import ApiError
from ..schemas import DocumentOut, FieldOut, FieldUpdate

router = APIRouter(prefix="/api/cases/{case_id}/documents", tags=["documents"])


async def _read_limited(upload: UploadFile, max_bytes: int) -> bytes:
    buf = bytearray()
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        buf += chunk
        if len(buf) > max_bytes:
            raise ApiError(413, "file_too_large", f"The file is larger than the {max_bytes // (1024 * 1024)} MB limit.")
    return bytes(buf)


@router.get("", response_model=list[DocumentOut], summary="List documents of a case")
def list_documents(case_id: int, db: Session = Depends(get_db)):
    return [services.doc_out(d) for d in services.get_case(db, case_id).documents]


@router.post("", response_model=DocumentOut, status_code=201,
             summary="Upload a PDF, PNG or JPEG (OCR runs in the background)")
async def upload_document(case_id: int, request: Request, background: BackgroundTasks, file: UploadFile = File(...),
                          doc_type: str = Form(...), db: Session = Depends(get_db),
                          settings: Settings = Depends(get_settings_dep)):
    case = services.get_case(db, case_id)
    content = await _read_limited(file, settings.max_upload_bytes)
    try:
        v = validate_upload(file.filename, file.content_type, content, max_bytes=settings.max_upload_bytes,
                            max_pdf_pages=settings.max_pdf_pages)
    except FileValidationError as exc:
        raise ApiError(422, exc.code, exc.message) from exc
    doc = services.store_document(db, settings, case, doc_type, sanitise_display_filename(file.filename), content, v)
    db.commit()
    background.add_task(services.process_document_job, request.app.state.session_factory, settings, doc.id)
    return services.doc_out(doc)


@router.get("/{doc_id}", response_model=DocumentOut, summary="Document detail with extracted fields")
def get_document(case_id: int, doc_id: int, db: Session = Depends(get_db)):
    return services.doc_out(services.get_document(db, case_id, doc_id))


@router.get("/{doc_id}/file", summary="View or download the stored document (protected: must belong to the case)")
def get_file(case_id: int, doc_id: int, download: bool = Query(False), db: Session = Depends(get_db),
             settings: Settings = Depends(get_settings_dep)):
    doc = services.get_document(db, case_id, doc_id)
    path = services.safe_path(settings.upload_dir, doc.stored_filename)
    if not path.is_file():
        raise ApiError(404, "file_missing", "The stored file is no longer available.")
    return FileResponse(path, media_type=doc.mime_type, filename=doc.original_filename,
                        content_disposition_type="attachment" if download else "inline",
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})


@router.delete("/{doc_id}", status_code=204, summary="Remove a document (requires confirm=true)")
def delete_document(case_id: int, doc_id: int, confirm: bool = Query(False), db: Session = Depends(get_db),
                    settings: Settings = Depends(get_settings_dep)):
    if not confirm:
        raise ApiError(400, "confirmation_required", "Removing a document must be confirmed (confirm=true).")
    services.delete_document(db, settings, services.get_document(db, case_id, doc_id))
    db.commit()


@router.post("/{doc_id}/retry-ocr", response_model=DocumentOut, status_code=202, summary="Retry OCR for a document")
def retry_ocr(case_id: int, doc_id: int, request: Request, background: BackgroundTasks, db: Session = Depends(get_db),
              settings: Settings = Depends(get_settings_dep)):
    doc = services.get_document(db, case_id, doc_id)
    if doc.processing_status in ("pending", "processing"):
        raise ApiError(409, "already_processing", "This document is already being processed.")
    doc.processing_status, doc.processing_error = "pending", None
    services.audit(db, doc.case, "ocr_retry", {"document_id": doc.id})
    services.mark_changed(db, doc.case, "OCR was rerun")
    if doc.case.status == "draft":
        services.set_status(db, doc.case, "processing", "system", "Document processing started", quiet=True)
    db.commit()
    background.add_task(services.process_document_job, request.app.state.session_factory, settings, doc.id)
    return services.doc_out(doc)


@router.put("/{doc_id}/fields/{field_name}", response_model=FieldOut,
            summary="Enter or correct a field value, or confirm the extracted value")
def update_field(case_id: int, doc_id: int, field_name: str, body: FieldUpdate, db: Session = Depends(get_db)):
    doc = services.get_document(db, case_id, doc_id)
    f = services.update_field(db, doc, field_name, body.value, body.confirm)
    db.commit()
    return services.field_out(f)
