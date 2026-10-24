"""Plain data structures used by the core modules."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Optional

RULES_VERSION = "demo-rules-1.0"

FIELD_LABELS: dict[str, str] = {
    "fdr_number": "FDR / receipt number",
    "bank_name": "Issuing bank",
    "branch": "Branch",
    "principal_amount": "Principal amount",
    "currency": "Currency",
    "issue_date": "Issue date",
    "maturity_date": "Maturity date",
    "beneficiary_name": "Institution / beneficiary name",
    "reference_number": "Application / reference number",
    "status_reference": "Status / reference note",
}
DATE_FIELDS = {"issue_date", "maturity_date"}

# Field statuses
ST_EXTRACTED = "extracted"    # produced by OCR, not yet reviewed by a person
ST_CONFIRMED = "confirmed"    # a person confirmed the OCR value as correct
ST_MANUAL = "manual"          # a person typed / corrected the value
ST_UNREADABLE = "unreadable"  # label seen but no usable value
USER_TRUSTED_STATUSES = {ST_CONFIRMED, ST_MANUAL}

# Finding outcomes (deliberately NOT "verified" / "genuine")
OUT_ISSUE = "issue_detected"
OUT_CONFIRM = "needs_confirmation"
OUT_NOT_CHECKED = "not_checked"
OUT_NO_ISSUE = "no_issue_detected"


@dataclass
class OcrLine:
    text: str
    confidence: Optional[float] = None  # 0-100, mean of word confidences


@dataclass
class OcrPage:
    page_number: int
    text: str
    lines: list[OcrLine] = field(default_factory=list)
    mean_confidence: Optional[float] = None


@dataclass
class ExtractedField:
    field_name: str
    value: Optional[str]            # normalised value (ISO date, decimal amount, ...) or None
    raw_value: Optional[str] = None  # text as printed on the document
    page_number: Optional[int] = None
    confidence: Optional[float] = None
    status: str = ST_EXTRACTED
    needs_confirmation: bool = True
    note: Optional[str] = None


@dataclass
class DocumentData:
    id: int
    filename: str
    doc_type: str
    processing_status: str = "processed"  # pending|processing|processed|failed
    sha256: Optional[str] = None


@dataclass
class FieldData:
    document_id: int
    field_name: str
    value: Optional[str]
    raw_value: Optional[str] = None
    page_number: Optional[int] = None
    confidence: Optional[float] = None
    status: str = ST_EXTRACTED
    needs_confirmation: bool = False
    note: Optional[str] = None


@dataclass
class ChecklistItem:
    doc_type: str
    label: str
    required: bool = True
    required_fields: list[str] = field(default_factory=list)


@dataclass
class CaseData:
    case_type: str
    institution_name: str = ""
    check_maturity: bool = False
    documents: list[DocumentData] = field(default_factory=list)
    fields: list[FieldData] = field(default_factory=list)


@dataclass
class EngineConfig:
    confidence_threshold: float = 80.0   # below this an OCR value needs confirmation
    approaching_maturity_days: int = 30


@dataclass
class Evidence:
    document_id: Optional[int]
    filename: Optional[str]
    doc_type: Optional[str]
    page: Optional[int]
    field_name: Optional[str]
    value: Optional[str]          # display value
    raw_value: Optional[str] = None
    confidence: Optional[float] = None
    trusted: Optional[bool] = None


@dataclass
class Finding:
    rule_id: str
    title: str
    outcome: str
    severity: str  # high | medium | low | info
    reason: str
    next_check: str
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VerificationResult:
    findings: list[Finding]
    rules_version: str
    generated_at: datetime
    overall_status: str
    summary: dict[str, int]
