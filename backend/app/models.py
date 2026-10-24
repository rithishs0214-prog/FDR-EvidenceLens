"""SQLAlchemy 2.x models. Cascades: deleting a case removes its documents/fields/findings;
deleting a document removes only that document's pages and fields. Audit events survive case
deletion (case_id becomes NULL, case_code is kept)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

CASE_STATUSES = ("draft", "processing", "needs_review", "awaiting_information", "review_completed")
PROCESSING_STATUSES = ("pending", "processing", "processed", "failed")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Stores naive UTC, returns timezone-aware UTC so JSON output carries an explicit offset."""
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        return None if value is None else value.replace(tzinfo=timezone.utc)


class Base(DeclarativeBase):
    pass


class CaseType(Base):
    __tablename__ = "case_types"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    check_maturity: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    rules: Mapped[list["ChecklistRule"]] = relationship(back_populates="case_type", cascade="all, delete-orphan",
                                                        order_by="ChecklistRule.id")


class ChecklistRule(Base):
    __tablename__ = "checklist_rules"
    __table_args__ = (UniqueConstraint("case_type_id", "doc_type"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    case_type_id: Mapped[int] = mapped_column(ForeignKey("case_types.id", ondelete="CASCADE"), index=True)
    doc_type: Mapped[str] = mapped_column(String(50))
    label: Mapped[str] = mapped_column(String(200))
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    required_fields: Mapped[list[str]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
    case_type: Mapped[CaseType] = relationship(back_populates="rules")


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (
        CheckConstraint("status IN ('draft','processing','needs_review','awaiting_information','review_completed')",
                        name="ck_case_status"),
        Index("ix_cases_status", "status"),
        Index("ix_cases_updated_at", "updated_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    case_code: Mapped[str] = mapped_column(String(30), unique=True, default="")
    institution_name: Mapped[str] = mapped_column(String(200))
    institution_ref: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    case_type_id: Mapped[int] = mapped_column(ForeignKey("case_types.id", ondelete="RESTRICT"), index=True)
    application_ref: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    analysis_stale: Mapped[bool] = mapped_column(Boolean, default=True)
    last_analysis_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    case_type: Mapped[CaseType] = relationship()
    documents: Mapped[list["Document"]] = relationship(back_populates="case", cascade="all, delete-orphan",
                                                       order_by="Document.id")
    findings: Mapped[list["Finding"]] = relationship(back_populates="case", cascade="all, delete-orphan",
                                                     order_by="Finding.id")
    status_history: Mapped[list["StatusHistory"]] = relationship(cascade="all, delete-orphan",
                                                                 order_by="StatusHistory.id")
    analysis_runs: Mapped[list["AnalysisRun"]] = relationship(cascade="all, delete-orphan",
                                                              order_by="AnalysisRun.id")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (CheckConstraint("processing_status IN ('pending','processing','processed','failed')",
                                      name="ck_doc_status"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    doc_type: Mapped[str] = mapped_column(String(50))
    original_filename: Mapped[str] = mapped_column(String(255))   # display only
    stored_filename: Mapped[str] = mapped_column(String(80), unique=True)  # random server-side name
    mime_type: Mapped[str] = mapped_column(String(50))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    page_count: Mapped[int] = mapped_column(Integer, default=1)
    processing_status: Mapped[str] = mapped_column(String(20), default="pending")
    processing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    case: Mapped[Case] = relationship(back_populates="documents")
    pages: Mapped[list["DocumentPage"]] = relationship(cascade="all, delete-orphan", order_by="DocumentPage.page_number")
    fields: Mapped[list["ExtractedFieldValue"]] = relationship(back_populates="document", cascade="all, delete-orphan",
                                                               order_by="ExtractedFieldValue.id")


class DocumentPage(Base):
    __tablename__ = "document_pages"
    __table_args__ = (UniqueConstraint("document_id", "page_number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, default="")   # OCR text; never written to logs
    mean_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class ExtractedFieldValue(Base):
    __tablename__ = "extracted_fields"
    __table_args__ = (
        UniqueConstraint("document_id", "field_name"),
        CheckConstraint("status IN ('extracted','confirmed','manual','unreadable')", name="ck_field_status"),
        Index("ix_fields_case", "case_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    field_name: Mapped[str] = mapped_column(String(50))
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="extracted")
    needs_confirmation: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
    document: Mapped[Document] = relationship(back_populates="fields")


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    run_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    rules_version: Mapped[str] = mapped_column(String(50))
    overall_status: Mapped[str] = mapped_column(String(30))
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Finding(Base):
    """Findings of the LATEST analysis run only (older runs' findings are replaced; run rows are kept)."""
    __tablename__ = "findings"
    __table_args__ = (Index("ix_findings_case_outcome", "case_id", "outcome"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    analysis_run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True)
    rule_id: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(300))
    outcome: Mapped[str] = mapped_column(String(30))
    severity: Mapped[str] = mapped_column(String(10))
    reason: Mapped[str] = mapped_column(Text)
    next_check: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    case: Mapped[Case] = relationship(back_populates="findings")


class StatusHistory(Base):
    __tablename__ = "status_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str] = mapped_column(String(30))
    actor: Mapped[str] = mapped_column(String(20), default="reviewer")  # reviewer | system
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class AuditEvent(Base):
    """Application-level log. NOT a tamper-proof regulatory audit trail."""
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_created", "created_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cases.id", ondelete="SET NULL"), nullable=True, index=True)
    case_code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    actor: Mapped[str] = mapped_column(String(20), default="user")
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)   # stored lower-case
    display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(300))           # PBKDF2-SHA256, never the password
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)


class AuthSession(Base):
    """Server-side login session. Only a hash of the cookie token is stored."""
    __tablename__ = "auth_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
