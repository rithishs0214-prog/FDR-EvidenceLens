export type CaseStatus = "draft" | "processing" | "needs_review" | "awaiting_information" | "review_completed";
export type Outcome = "issue_detected" | "needs_confirmation" | "not_checked" | "no_issue_detected";

export interface Page<T> { items: T[]; total: number; page: number; page_size: number }

export interface CaseSummary {
  id: number; case_code: string; institution_name: string; case_type_id: number; case_type_name: string;
  application_ref: string | null; status: CaseStatus; is_demo: boolean; document_count: number;
  analysis_stale: boolean; last_analysis_at: string | null; has_missing_documents: boolean;
  has_discrepancies: boolean; issue_count: number; needs_confirmation_count: number;
  created_at: string; updated_at: string;
}
export interface FieldOut {
  id: number; document_id: number; field_name: string; label: string; value: string | null; raw_value: string | null;
  page_number: number | null; confidence: number | null; status: string; needs_confirmation: boolean;
  note: string | null; updated_at: string;
}
export interface DocumentOut {
  id: number; case_id: number; doc_type: string; doc_type_label: string; original_filename: string; mime_type: string;
  size_bytes: number; page_count: number; processing_status: string; processing_error: string | null;
  uploaded_at: string; fields: FieldOut[];
}
export interface StatusHistoryOut { id: number; from_status: string | null; to_status: string; actor: string; note: string | null; created_at: string }
export interface CaseDetail extends CaseSummary {
  institution_ref: string | null; notes: string | null; reviewer_notes: string | null; review_outcome: string | null;
  documents: DocumentOut[]; status_history: StatusHistoryOut[]; ocr_available: boolean; ocr_message: string;
}
export interface Evidence {
  document_id: number | null; filename: string | null; doc_type: string | null; page: number | null;
  field_name: string | null; value: string | null; raw_value: string | null; confidence: number | null; trusted: boolean | null;
}
export interface FindingOut {
  id: number; rule_id: string; title: string; outcome: Outcome; severity: string; reason: string; next_check: string; evidence: Evidence[];
}
export interface ChecklistStatus { doc_type: string; label: string; required: boolean; present: boolean; document_ids: number[] }
export interface NeedsConfirmation {
  document_id: number; filename: string; field_name: string; label: string; value: string | null;
  page: number | null; confidence: number | null; status: string; note: string | null;
}
export interface AnalysisOut {
  has_run: boolean; stale: boolean; last_analysis_at: string | null; rules_version: string | null;
  overall_status: Outcome | null; summary: Record<string, number>; checklist: ChecklistStatus[];
  findings: FindingOut[]; fields_needing_confirmation: NeedsConfirmation[]; disclaimer: string;
}
export interface RuleOut { id: number; doc_type: string; label: string; required: boolean; required_fields: string[] }
export interface CaseTypeOut { id: number; name: string; description: string; check_maturity: boolean; rules: RuleOut[] }
export interface DashboardOut {
  total_cases: number; needs_review: number; missing_documents: number; unresolved_discrepancies: number;
  by_status: Record<string, number>; recent_cases: CaseSummary[];
}
export interface AuditEventOut { id: number; case_id: number | null; case_code: string | null; action: string; actor: string; details: Record<string, unknown>; created_at: string }
export interface AppConfig {
  max_upload_mb: number; max_pdf_pages: number; supported_formats: string; ocr_confidence_threshold: number;
  approaching_maturity_days: number; rules_version: string; doc_type_labels: Record<string, string>;
  field_labels: Record<string, string>; environment: string; demo_endpoints_enabled: boolean; notice: string;
}
export interface Health { status: string; environment: string; ocr_available: boolean; ocr_message: string; demo_endpoints_enabled: boolean; rules_version: string }
export interface ReportOut {
  case_code: string; institution_name: string; institution_ref: string | null; application_ref: string | null;
  case_type_name: string; status: CaseStatus; generated_at: string; last_analysis_at: string | null; analysis_stale: boolean;
  rules_version: string | null; is_demo: boolean;
  documents: { id: number; filename: string; type: string; uploaded_at: string; processing_status: string; pages: number; sha256_prefix: string }[];
  fields: { document: string; field: string; value: string | null; page: number | null; confidence: number | null; confirmation: string; confirmed: boolean }[];
  checklist: ChecklistStatus[]; findings: FindingOut[]; next_checks: string[]; reviewer_notes: string | null;
  review_outcome: string | null; status_history: StatusHistoryOut[]; limitations: string[];
}
