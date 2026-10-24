import { get } from "../api";
import { ErrorBox, fmtDate, Icon, Loading, Notice, OUTCOME_LABEL, STATUS_LABEL } from "../components/ui";
import { useAsync } from "../hooks";
import type { Outcome, ReportOut } from "../types";
import { useCase } from "./CaseLayout";
import { FindingCard } from "./ResultsTab";

const ORDER: Outcome[] = ["issue_detected", "needs_confirmation", "not_checked", "no_issue_detected"];

export default function Report() {
  const { detail } = useCase();
  const { data: r, error, loading, reload } = useAsync(() => get<ReportOut>(`/api/cases/${detail.id}/report`), [detail.id, detail.updated_at]);
  if (loading && !r) return <Loading label="Preparing report…" />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!r) return null;
  return (
    <div className="report">
      <div className="page-actions no-print" style={{ marginBottom: ".75rem" }}>
        <button className="btn btn-primary" onClick={() => window.print()}><Icon name="print" /> Print / Save as PDF</button>
        <span className="muted small">Choose “Save as PDF” in the browser print dialog. Layout is set for A4.</span>
      </div>
      {r.is_demo && <div className="report-banner">SYNTHETIC DEMO DATA — fictional documents</div>}
      <h1>FDR EvidenceLens — Case Report</h1>
      <p className="muted"><strong>Decision-support report from a prototype tool. This is not an official AICTE document and does not authenticate any FDR.</strong></p>
      {r.analysis_stale && <Notice kind="warn">Data changed after the last analysis; rerun the analysis before relying on this report.</Notice>}

      <h2>Case</h2>
      <table><tbody>
        <tr><th>Case ID</th><td>{r.case_code}</td><th>Generated</th><td>{fmtDate(r.generated_at)}</td></tr>
        <tr><th>Institution</th><td>{r.institution_name}</td><th>Case type</th><td>{r.case_type_name}</td></tr>
        <tr><th>Institution ref.</th><td>{r.institution_ref ?? "—"}</td><th>Application ref.</th><td>{r.application_ref ?? "—"}</td></tr>
        <tr><th>Status</th><td>{STATUS_LABEL[r.status]}</td><th>Last analysis</th><td>{fmtDate(r.last_analysis_at)}</td></tr>
        <tr><th>Rules version</th><td>{r.rules_version ?? "not analysed"}</td><th></th><td></td></tr>
      </tbody></table>

      <h2>Document inventory</h2>
      {r.documents.length === 0 ? <p>No documents attached.</p> : (
        <table><thead><tr><th>File</th><th>Type</th><th>Uploaded</th><th>Pages</th><th>Processing</th><th>SHA-256 (start)</th></tr></thead>
          <tbody>{r.documents.map((d) => <tr key={d.id}><td>{d.filename}</td><td>{d.type}</td><td>{fmtDate(d.uploaded_at)}</td><td>{d.pages}</td><td>{d.processing_status}</td><td>{d.sha256_prefix}</td></tr>)}</tbody></table>
      )}

      <h2>Extracted fields and confirmation status</h2>
      {r.fields.length === 0 ? <p>No fields recorded.</p> : (
        <table><thead><tr><th>Document</th><th>Field</th><th>Value</th><th>Page</th><th>Confidence</th><th>Status</th></tr></thead>
          <tbody>{r.fields.map((f, i) => <tr key={i}><td>{f.document}</td><td>{f.field}</td><td>{f.value ?? "unreadable"}</td><td>{f.page ?? "—"}</td><td>{f.confidence !== null ? `${f.confidence.toFixed(0)}%` : "n/a"}</td><td>{f.confirmation}</td></tr>)}</tbody></table>
      )}

      <h2>Required-document checklist (demonstration checklist)</h2>
      <table><thead><tr><th>Document</th><th>Requirement</th><th>Result</th></tr></thead>
        <tbody>{r.checklist.map((c) => <tr key={c.doc_type}><td>{c.label}</td><td>{c.required ? "Required" : "Optional"}</td><td>{c.present ? "Attached" : c.required ? "MISSING" : "Not attached"}</td></tr>)}</tbody></table>

      <h2>Findings</h2>
      {r.findings.length === 0 && <p>No analysis has been run for this case.</p>}
      {ORDER.map((o) => {
        const list = r.findings.filter((f) => f.outcome === o);
        return list.length > 0 && <section key={o}><h3>{OUTCOME_LABEL[o]} ({list.length})</h3>{list.map((f) => <FindingCard key={f.id} f={f} />)}</section>;
      })}

      <h2>Suggested next checks</h2>
      {r.next_checks.length === 0 ? <p>None suggested by the configured rules.</p> : <ol>{r.next_checks.map((n, i) => <li key={i}>{n}</li>)}</ol>}

      <h2>Human review</h2>
      <p><strong>Recorded status:</strong> {STATUS_LABEL[r.status]}</p>
      <p><strong>Reviewer notes:</strong> {r.reviewer_notes ?? "—"}</p>
      <p><strong>Recorded outcome note:</strong> {r.review_outcome ?? "—"}</p>
      <table><thead><tr><th>When</th><th>Change</th><th>By</th><th>Note</th></tr></thead>
        <tbody>{r.status_history.map((h) => <tr key={h.id}><td>{fmtDate(h.created_at)}</td><td>{h.from_status ? `${STATUS_LABEL[h.from_status]} → ` : ""}{STATUS_LABEL[h.to_status]}</td><td>{h.actor}</td><td>{h.note ?? "—"}</td></tr>)}</tbody></table>

      <h2>Important limitations</h2>
      <ul>{r.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul>
    </div>
  );
}
