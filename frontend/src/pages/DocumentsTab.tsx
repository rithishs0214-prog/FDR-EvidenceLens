import { useRef, useState } from "react";
import { ApiClientError, del, fileUrl, post, put, uploadDocument } from "../api";
import { ConfirmDialog, fmtDate, formatBytes, Icon, Notice } from "../components/ui";
import { useAsync } from "../hooks";
import { get } from "../api";
import type { AppConfig, CaseTypeOut, DocumentOut, FieldOut } from "../types";
import { useCase } from "./CaseLayout";

const FIELD_ORDER = ["fdr_number", "bank_name", "branch", "principal_amount", "currency", "issue_date", "maturity_date", "beneficiary_name", "reference_number", "status_reference"];
const LABELS: Record<string, string> = {
  fdr_number: "FDR / receipt number", bank_name: "Issuing bank", branch: "Branch", principal_amount: "Principal amount", currency: "Currency",
  issue_date: "Issue date", maturity_date: "Maturity date", beneficiary_name: "Institution / beneficiary name",
  reference_number: "Application / reference number", status_reference: "Status / reference note",
};
const PROC: Record<string, string> = { pending: "Queued", processing: "Processing", processed: "Processed", failed: "Failed" };

function FieldEditor({ caseId, doc, name, field, threshold, onChanged }: {
  caseId: number; doc: DocumentOut; name: string; field?: FieldOut; threshold: number; onChanged: () => void;
}) {
  const [value, setValue] = useState(field?.value ?? "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const trusted = field && field.value !== null && (field.status === "confirmed" || field.status === "manual" ||
    (!field.needs_confirmation && field.confidence !== null && field.confidence >= threshold));
  async function save(confirm: boolean) {
    setBusy(true); setErr(null);
    try {
      await put(`/api/cases/${caseId}/documents/${doc.id}/fields/${name}`, confirm ? { confirm: true } : { value });
      onChanged();
    } catch (e) { setErr(e instanceof Error ? e.message : "Could not save."); } finally { setBusy(false); }
  }
  const id = `f-${doc.id}-${name}`;
  return (
    <div className="field-row">
      <div>
        <label htmlFor={id} style={{ marginBottom: 0 }}>{LABELS[name] ?? name}</label>
        <span className="muted small">
          {!field ? "Not found — enter manually if shown on the document" :
            <>{field.status === "manual" ? "Entered by reviewer" : field.status === "confirmed" ? "Confirmed by reviewer" :
              field.value === null ? "Unreadable" : "OCR value"}
              {field.confidence !== null && ` · confidence ${field.confidence.toFixed(0)}%`}
              {field.page_number !== null && ` · page ${field.page_number}`}</>}
        </span>
        {field && !trusted && <div><span className="badge outcome-needs_confirmation">Needs confirmation</span></div>}
        {field?.note && <div className="muted small">{field.note}</div>}
        {err && <div className="field-error" role="alert">{err}</div>}
      </div>
      <input id={id} type="text" value={value} onChange={(e) => setValue(e.target.value)} placeholder={field?.value === null ? "Enter value" : ""} />
      <div className="page-actions">
        <button className="btn btn-small" disabled={busy || !value.trim() || value.trim() === (field?.value ?? "")} onClick={() => save(false)}>Save</button>
        {field && field.value !== null && !trusted && <button className="btn btn-small" disabled={busy} onClick={() => save(true)}>Confirm as correct</button>}
      </div>
    </div>
  );
}

export default function DocumentsTab() {
  const { detail, reload } = useCase();
  const types = useAsync(() => get<CaseTypeOut[]>("/api/case-types"), []);
  const cfg = useAsync(() => get<AppConfig>("/api/config"), []);
  const [open, setOpen] = useState<number | null>(null);
  const [toDelete, setToDelete] = useState<DocumentOut | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "success" | "warn"; text: string } | null>(null);
  const [upType, setUpType] = useState("");
  const [progress, setProgress] = useState<number | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const rules = types.data?.find((t) => t.id === detail.case_type_id)?.rules ?? [];
  const options = [...rules.map((r) => ({ value: r.doc_type, label: r.label })), { value: "other", label: "Other supporting document" }];
  const threshold = cfg.data?.ocr_confidence_threshold ?? 80;
  const maxMb = cfg.data?.max_upload_mb ?? 10;

  async function uploadSelected(file: File | undefined) {
    if (!file) return;
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (![".pdf", ".png", ".jpg", ".jpeg"].includes(ext)) { setMsg({ kind: "warn", text: "Unsupported file type. Use PDF, PNG or JPEG." }); return; }
    if (file.size > maxMb * 1024 * 1024) { setMsg({ kind: "warn", text: `The file is larger than ${maxMb} MB.` }); return; }
    setMsg(null); setProgress(0);
    try {
      await uploadDocument(detail.id, file, upType || options[0].value, setProgress);
      setMsg({ kind: "success", text: "Uploaded. Text extraction is running; this page updates automatically." });
      reload();
    } catch (e) { setMsg({ kind: "warn", text: e instanceof Error ? e.message : "Upload failed." }); } finally { setProgress(null); if (fileRef.current) fileRef.current.value = ""; }
  }

  async function removeDoc() {
    if (!toDelete) return;
    setBusy(true);
    try { await del(`/api/cases/${detail.id}/documents/${toDelete.id}?confirm=true`); setToDelete(null); setMsg({ kind: "success", text: "Document removed. The case itself was not deleted." }); reload(); }
    catch (e) { setMsg({ kind: "warn", text: e instanceof Error ? e.message : "Could not remove the document." }); setToDelete(null); }
    finally { setBusy(false); }
  }
  async function retry(d: DocumentOut) {
    try { await post(`/api/cases/${detail.id}/documents/${d.id}/retry-ocr`); reload(); }
    catch (e) { setMsg({ kind: "warn", text: e instanceof ApiClientError ? e.message : "Could not retry." }); }
  }

  return (
    <div>
      {!detail.ocr_available && <Notice kind="warn"><strong>OCR is not available.</strong> {detail.ocr_message} You can still enter every field manually below. See the README for Tesseract setup.</Notice>}
      {msg && <Notice kind={msg.kind}>{msg.text}</Notice>}
      {detail.analysis_stale && detail.documents.length > 0 && <Notice kind="info">Data has changed since the last analysis. Open <strong>Verification results</strong> and run the analysis again.</Notice>}

      <h2>Uploaded documents</h2>
      {detail.documents.length === 0 ? (
        <div className="state empty">No documents yet. Upload an FDR scan and supporting documents below.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>File</th><th>Type</th><th>Uploaded</th><th>Processing</th><th>Actions</th></tr></thead>
            <tbody>
              {detail.documents.map((d) => (
                <tr key={d.id}>
                  <td>{d.original_filename}<div className="muted small">{formatBytes(d.size_bytes)} · {d.page_count} page(s)</div></td>
                  <td>{d.doc_type_label}</td>
                  <td>{fmtDate(d.uploaded_at)}</td>
                  <td>
                    <span className={`badge ${d.processing_status === "failed" ? "outcome-issue_detected" : d.processing_status === "processed" ? "outcome-no_issue_detected" : "badge-processing"}`}>{PROC[d.processing_status] ?? d.processing_status}</span>
                    {d.processing_error && <div className="field-error">{d.processing_error}</div>}
                  </td>
                  <td>
                    <div className="page-actions">
                      <a className="btn btn-small" href={fileUrl(detail.id, d.id)} target="_blank" rel="noreferrer"><Icon name="eye" /> View</a>
                      <a className="btn btn-small" href={fileUrl(detail.id, d.id, true)}>Download</a>
                      <button className="btn btn-small" onClick={() => setOpen(open === d.id ? null : d.id)} aria-expanded={open === d.id}>{open === d.id ? "Hide fields" : "Fields"}</button>
                      {(d.processing_status === "failed" || d.processing_status === "processed") && <button className="btn btn-small" onClick={() => retry(d)}><Icon name="refresh" /> Retry OCR</button>}
                      <button className="btn btn-small" onClick={() => setToDelete(d)}><Icon name="trash" /> Remove</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {detail.documents.map((d) => open === d.id && (
        <section key={d.id} className="panel" aria-label={`Fields for ${d.original_filename}`}>
          <h3>Fields — {d.original_filename}</h3>
          <p className="muted small">OCR values are never treated as proof that a document is genuine. Confirm or correct each value against the original; a value you save or confirm is trusted by the comparison rules.</p>
          {FIELD_ORDER.map((n) => (
            <FieldEditor key={`${d.id}-${n}-${d.fields.find((f) => f.field_name === n)?.updated_at ?? "none"}`} caseId={detail.id} doc={d} name={n}
                         field={d.fields.find((f) => f.field_name === n)} threshold={threshold} onChanged={reload} />
          ))}
        </section>
      ))}

      <h2>Add a document</h2>
      <div className="panel">
        <div className="toolbar">
          <div>
            <label htmlFor="up-type">Document type</label>
            <select id="up-type" value={upType} onChange={(e) => setUpType(e.target.value)}>
              {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="up-file">File <span className="hint">({cfg.data?.supported_formats ?? "PDF, PNG or JPEG"}, up to {maxMb} MB)</span></label>
            <input id="up-file" ref={fileRef} type="file" accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
                   disabled={progress !== null} onChange={(e) => uploadSelected(e.target.files?.[0])} />
          </div>
        </div>
        {progress !== null && <p><progress max={100} value={progress} aria-label="Upload progress" /> {progress}%</p>}
      </div>

      {toDelete && (
        <ConfirmDialog title="Remove this document?" confirmLabel="Remove document" danger busy={busy} onConfirm={removeDoc} onCancel={() => setToDelete(null)}>
          <p><strong>{toDelete.original_filename}</strong> and the fields extracted from it will be deleted. The case and its other documents are kept. This is recorded in the audit history and the analysis will need to be run again.</p>
        </ConfirmDialog>
      )}
    </div>
  );
}
