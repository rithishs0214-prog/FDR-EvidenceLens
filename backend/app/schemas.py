from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


def _blank_to_none(v):
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


class CaseCreate(BaseModel):
    institution_name: str = Field(min_length=2, max_length=200)
    institution_ref: Optional[str] = Field(default=None, max_length=100)
    case_type_id: int
    application_ref: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=5000)

    @field_validator("institution_name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v) < 2:
            raise ValueError("Institution name must contain at least 2 characters.")
        return v

    @field_validator("institution_ref", "application_ref", "notes")
    @classmethod
    def _optional_blank(cls, v):
        return _blank_to_none(v)


class CaseUpdate(BaseModel):
    institution_name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    institution_ref: Optional[str] = Field(default=None, max_length=100)
    application_ref: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=5000)
    reviewer_notes: Optional[str] = Field(default=None, max_length=5000)


class StatusChange(BaseModel):
    status: Literal["needs_review", "awaiting_information", "review_completed"]
    note: Optional[str] = Field(default=None, max_length=2000)
    confirm: bool = False


class FieldUpdate(BaseModel):
    value: Optional[str] = Field(default=None, max_length=300)
    confirm: bool = False


class RuleUpdate(BaseModel):
    label: Optional[str] = Field(default=None, min_length=2, max_length=200)
    required: Optional[bool] = None
    required_fields: Optional[list[str]] = None


class CaseTypeUpdate(BaseModel):
    check_maturity: Optional[bool] = None


class FieldOut(ORM):
    id: int
    document_id: int
    field_name: str
    label: str = ""
    value: Optional[str]
    raw_value: Optional[str]
    page_number: Optional[int]
    confidence: Optional[float]
    status: str
    needs_confirmation: bool
    note: Optional[str]
    updated_at: datetime


class DocumentOut(ORM):
    id: int
    case_id: int
    doc_type: str
    doc_type_label: str = ""
    original_filename: str
    mime_type: str
    size_bytes: int
    page_count: int
    processing_status: str
    processing_error: Optional[str]
    uploaded_at: datetime
    fields: list[FieldOut] = []


class FindingOut(ORM):
    id: int
    rule_id: str
    title: str
    outcome: str
    severity: str
    reason: str
    next_check: str
    evidence: list[dict[str, Any]]


class StatusHistoryOut(ORM):
    id: int
    from_status: Optional[str]
    to_status: str
    actor: str
    note: Optional[str]
    created_at: datetime


class AuditEventOut(ORM):
    id: int
    case_id: Optional[int]
    case_code: Optional[str]
    action: str
    actor: str
    details: dict[str, Any]
    created_at: datetime


class CaseSummary(BaseModel):
    id: int
    case_code: str
    institution_name: str
    case_type_id: int
    case_type_name: str
    application_ref: Optional[str]
    status: str
    is_demo: bool
    document_count: int
    analysis_stale: bool
    last_analysis_at: Optional[datetime]
    has_missing_documents: bool
    has_discrepancies: bool
    issue_count: int
    needs_confirmation_count: int
    created_at: datetime
    updated_at: datetime


class CaseDetail(CaseSummary):
    institution_ref: Optional[str]
    notes: Optional[str]
    reviewer_notes: Optional[str]
    review_outcome: Optional[str]
    documents: list[DocumentOut]
    status_history: list[StatusHistoryOut]
    ocr_available: bool
    ocr_message: str


class ChecklistStatus(BaseModel):
    doc_type: str
    label: str
    required: bool
    present: bool
    document_ids: list[int]


class AnalysisOut(BaseModel):
    has_run: bool
    stale: bool
    last_analysis_at: Optional[datetime]
    rules_version: Optional[str]
    overall_status: Optional[str]
    summary: dict[str, int]
    checklist: list[ChecklistStatus]
    findings: list[FindingOut]
    fields_needing_confirmation: list[dict[str, Any]]
    disclaimer: str


class RuleOut(ORM):
    id: int
    doc_type: str
    label: str
    required: bool
    required_fields: list[str]


class CaseTypeOut(ORM):
    id: int
    name: str
    description: str
    check_maturity: bool
    rules: list[RuleOut]


class DashboardOut(BaseModel):
    total_cases: int
    needs_review: int
    missing_documents: int
    unresolved_discrepancies: int
    by_status: dict[str, int]
    recent_cases: list[CaseSummary]


class ReportOut(BaseModel):
    case_code: str
    institution_name: str
    institution_ref: Optional[str]
    application_ref: Optional[str]
    case_type_name: str
    status: str
    generated_at: datetime
    last_analysis_at: Optional[datetime]
    analysis_stale: bool
    rules_version: Optional[str]
    is_demo: bool
    documents: list[dict[str, Any]]
    fields: list[dict[str, Any]]
    checklist: list[ChecklistStatus]
    findings: list[FindingOut]
    next_checks: list[str]
    reviewer_notes: Optional[str]
    review_outcome: Optional[str]
    status_history: list[StatusHistoryOut]
    limitations: list[str]


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    username: str
    display_name: Optional[str] = None
