import { useState } from "react";
import { Link } from "react-router-dom";
import { get, post } from "../api";
import { ErrorBox, fmtDate, Icon, Loading, Notice, OUTCOME_LABEL, OutcomeBadge } from "../components/ui";
import { useAsync } from "../hooks";
import type { AnalysisOut, FindingOut, Outcome } from "../types";
import { useCase } from "./CaseLayout";

const ORDER: Outcome[] = ["issue_detected", "needs_confirmation", "not_checked", "no_issue_detected"];

export function FindingCard({ f }: { f: FindingOut }) {
  const hasValues = f.evidence.some((e) => e.value !== null);
  return (
    <article className={`finding ${f.outcome}`}>
      <h3>{f.title}</h3>
      <div><OutcomeBadge outcome={f.outcome} /> <span className="rule-id">Rule {f.rule_id}</span></div>
      <p><strong>Why this was flagged:</strong> {f.reason}</p>
      {f.evidence.length > 0 && (
        <div className="table-wrap">
          <table>
            <caption className="sr-only">Evidence for {f.title}</caption>
            <thead><tr><th>Source document</th><th>Page</th><th>Field</th>{hasValues && <th>Value found</th>}<th>OCR confidence</th></tr></thead>
            <tbody>
              {f.evidence.map((e, i) => (
                <tr key={i}>
                  <td>{e.filename ?? "—"}</td>
                  <td>{e.page ?? "unknown"}</td>
                  <td>{e.field_name ?? "—"}</td>
                  {hasValues && <td><strong>{e.value ?? "—"}</strong>{e.trusted === false && <div className="muted small">unconfirmed</div>}</td>}
                  <td>{e.confidence !== null ? `${e.confidence.toFixed(0)}%` : "n/a"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="next"><strong>Suggested next check:</strong> {f.next_check}</p>
    </article>
  );
}

export default function ResultsTab() {
  const { detail, reload } = useCase();
  const { data, error, loading, reload: reloadAnalysis } = useAsync(() => get<AnalysisOut>(`/api/cases/${detail.id}/analysis`), [detail.id, detail.updated_at]);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const processing = detail.documents.some((d) => d.processing_status === "pending" || d.processing_status === "processing");

  async function run() {
    setRunning(true); setRunError(null);
    try { await post(`/api/cases/${detail.id}/analysis`); reloadAnalysis(); reload(); }
    catch (e) { setRunError(e instanceof Error ? e.message : "Analysis failed."); } finally { setRunning(false); }
  }

  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reloadAnalysis} />;
  if (!data) return null;
  const byOutcome = (o: Outcome) => data.findings.filter((f) => f.outcome === o);

  return (
    <div>
      <div className="panel">
        <div className="page-header" style={{ marginBottom: 0 }}>
          <div>
            <strong>Case status:</strong> {detail.status.replace(/_/g, " ")}<br />
            <span className="muted small">Last analysis: {fmtDate(data.last_analysis_at)} · Rules version: {data.rules_version ?? "—"}</span>
          </div>
          <button className="btn btn-primary" onClick={run} disabled={running || processing || detail.documents.length === 0}>
            <Icon name="refresh" /> {data.has_run ? "Rerun analysis" : "Run analysis"}
          </button>
        </div>
        {processing && <p className="muted small">Documents are still being processed. You can run the analysis when they finish.</p>}
        {detail.documents.length === 0 && <p className="muted small">Upload at least one document first.</p>}
      </div>
      {runError && <ErrorBox message={runError} />}
      <Notice kind="info">{data.disclaimer}</Notice>
      {!data.has_run && <div className="state empty">No analysis has been run yet. Choose “Run analysis” to check the documents against the configured rules.</div>}
      {data.has_run && data.stale && <Notice kind="warn"><strong>These results are out of date.</strong> Documents, fields or rules changed after the last analysis. Rerun the analysis.</Notice>}

      {data.has_run && (
        <>
          <p>
            {ORDER.map((o) => <span key={o} style={{ marginRight: ".75rem" }}><OutcomeBadge outcome={o} /> <strong>{data.summary[o] ?? 0}</strong></span>)}
          </p>

          <h2>Required-document checklist</h2>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Document</th><th>Requirement (demo checklist)</th><th>Result</th></tr></thead>
              <tbody>
                {data.checklist.map((c) => (
                  <tr key={c.doc_type}>
                    <td>{c.label}</td><td>{c.required ? "Required" : "Optional"}</td>
                    <td>{c.present ? <span className="badge outcome-no_issue_detected">Attached</span> : c.required ? <span className="badge badge-missing">Missing</span> : <span className="badge outcome-not_checked">Not attached</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {data.fields_needing_confirmation.length > 0 && (
            <>
              <h2>Values requiring confirmation</h2>
              <p className="muted">These values are unreadable, low-confidence or not yet confirmed. <Link to={`/cases/${detail.id}`}>Open Documents &amp; fields</Link> to confirm or correct them, then rerun the analysis.</p>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Document</th><th>Field</th><th>Value</th><th>Page</th><th>Confidence</th></tr></thead>
                  <tbody>
                    {data.fields_needing_confirmation.map((f, i) => (
                      <tr key={i}><td>{f.filename}</td><td>{f.label}</td><td>{f.value ?? <em>unreadable</em>}</td><td>{f.page ?? "unknown"}</td><td>{f.confidence !== null ? `${f.confidence.toFixed(0)}%` : "n/a"}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {ORDER.map((o) => byOutcome(o).length > 0 && (
            <section key={o}>
              <h2>{OUTCOME_LABEL[o]} ({byOutcome(o).length})</h2>
              {byOutcome(o).map((f) => <FindingCard key={f.id} f={f} />)}
            </section>
          ))}
        </>
      )}
    </div>
  );
}
