import { FormEvent, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiClientError, get, post, uploadDocument } from "../api";
import { ErrorBox, formatBytes, Loading, Notice, PageHeader } from "../components/ui";
import { useAsync } from "../hooks";
import type { AppConfig, CaseDetail, CaseTypeOut } from "../types";

interface Pick { id: number; file: File; docType: string; progress: number; error?: string; done?: boolean }
const EXT = [".pdf", ".png", ".jpg", ".jpeg"];

export default function NewCase() {
  const nav = useNavigate();
  const types = useAsync(() => get<CaseTypeOut[]>("/api/case-types"), []);
  const cfg = useAsync(() => get<AppConfig>("/api/config"), []);
  const [name, setName] = useState("");
  const [instRef, setInstRef] = useState("");
  const [typeId, setTypeId] = useState("");
  const [appRef, setAppRef] = useState("");
  const [notes, setNotes] = useState("");
  const [picks, setPicks] = useState<Pick[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [createdId, setCreatedId] = useState<number | null>(null);
  const nextId = useRef(1);

  const caseType = types.data?.find((t) => String(t.id) === typeId);
  const docOptions = [...(caseType?.rules.map((r) => ({ value: r.doc_type, label: r.label })) ?? []), { value: "other", label: "Other supporting document" }];
  const maxMb = cfg.data?.max_upload_mb ?? 10;

  function addFiles(list: FileList | null) {
    if (!list) return;
    const added: Pick[] = [];
    const errs = { ...errors };
    delete errs.files;
    for (const f of Array.from(list)) {
      const ext = f.name.slice(f.name.lastIndexOf(".")).toLowerCase();
      if (!EXT.includes(ext)) { errs.files = `“${f.name}” is not a supported type. Use PDF, PNG or JPEG.`; continue; }
      if (f.size > maxMb * 1024 * 1024) { errs.files = `“${f.name}” is larger than ${maxMb} MB.`; continue; }
      added.push({ id: nextId.current++, file: f, docType: docOptions[0]?.value ?? "other", progress: 0 });
    }
    setErrors(errs);
    setPicks((p) => [...p, ...added]);
  }

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (name.trim().length < 2) e.name = "Enter the institution name (at least 2 characters).";
    if (!typeId) e.type = "Choose a case type.";
    setErrors((old) => ({ ...e, ...(old.files ? { files: old.files } : {}) }));
    return Object.keys(e).length === 0;
  }

  async function submit(ev: FormEvent) {
    ev.preventDefault();
    if (submitting || !validate()) return;
    setSubmitting(true); setFormError(null);
    try {
      let id = createdId;
      if (id === null) {
        const c = await post<CaseDetail>("/api/cases", {
          institution_name: name, institution_ref: instRef, case_type_id: Number(typeId), application_ref: appRef, notes,
        });
        id = c.id; setCreatedId(id);
      }
      let failed = 0;
      for (const p of picks.filter((x) => !x.done)) {
        try {
          await uploadDocument(id, p.file, p.docType, (pct) => setPicks((all) => all.map((x) => (x.id === p.id ? { ...x, progress: pct } : x))));
          setPicks((all) => all.map((x) => (x.id === p.id ? { ...x, done: true, error: undefined } : x)));
        } catch (e) {
          failed++;
          setPicks((all) => all.map((x) => (x.id === p.id ? { ...x, error: e instanceof Error ? e.message : "Upload failed." } : x)));
        }
      }
      if (failed === 0) nav(`/cases/${id}`);
      else setFormError(`The case was created, but ${failed} file(s) could not be uploaded. Fix or remove them and submit again, or open the case.`);
    } catch (e) {
      setFormError(e instanceof ApiClientError ? e.message : "Could not create the case.");
    } finally {
      setSubmitting(false);
    }
  }

  if (types.loading || cfg.loading) return <Loading />;
  if (types.error) return <ErrorBox message={types.error} onRetry={types.reload} />;

  return (
    <div>
      <PageHeader title="Create New Case" subtitle="Enter case details and upload the FDR scan and supporting documents." />
      <Notice kind="warn">Use <strong>fictional or consented</strong> documents only. This local prototype has only a basic login (no roles or MFA) and is not production-ready.</Notice>
      <form onSubmit={submit} noValidate aria-busy={submitting}>
        <div className="row">
          <div>
            <label htmlFor="name">Institution name <span className="hint">(required)</span></label>
            <input id="name" type="text" value={name} onChange={(e) => setName(e.target.value)} aria-invalid={!!errors.name} aria-describedby="name-err" maxLength={200} disabled={createdId !== null} />
            {errors.name && <div id="name-err" className="field-error">{errors.name}</div>}
          </div>
          <div>
            <label htmlFor="iref">Institution reference ID <span className="hint">(optional)</span></label>
            <input id="iref" type="text" value={instRef} onChange={(e) => setInstRef(e.target.value)} maxLength={100} disabled={createdId !== null} />
          </div>
        </div>
        <div className="row">
          <div>
            <label htmlFor="ctype">Case type <span className="hint">(required)</span></label>
            <select id="ctype" value={typeId} onChange={(e) => { setTypeId(e.target.value); setPicks((p) => p.map((x) => ({ ...x, docType: "other" }))); }} aria-invalid={!!errors.type} disabled={createdId !== null}>
              <option value="">Select a case type…</option>
              {types.data?.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
            {errors.type && <div className="field-error">{errors.type}</div>}
            {caseType && <p className="hint">{caseType.description}</p>}
          </div>
          <div>
            <label htmlFor="aref">Application / reference number <span className="hint">(optional)</span></label>
            <input id="aref" type="text" value={appRef} onChange={(e) => setAppRef(e.target.value)} maxLength={100} disabled={createdId !== null} />
          </div>
        </div>
        <div style={{ marginBottom: ".9rem" }}>
          <label htmlFor="notes">Notes <span className="hint">(optional)</span></label>
          <textarea id="notes" rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={5000} disabled={createdId !== null} />
        </div>

        <fieldset className="panel">
          <legend><strong>Documents</strong></legend>
          <p className="hint">Supported: {cfg.data?.supported_formats ?? "PDF, PNG or JPEG"} · up to {maxMb} MB each · PDFs up to {cfg.data?.max_pdf_pages ?? 10} pages. You can also add documents after creating the case.</p>
          <label htmlFor="files" className="btn">Choose files…</label>
          <input id="files" type="file" multiple accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" style={{ position: "absolute", opacity: 0, width: 1, height: 1 }}
                 onChange={(e) => { addFiles(e.target.files); e.target.value = ""; }} />
          {errors.files && <div className="field-error" role="alert">{errors.files}</div>}
          {picks.length > 0 && (
            <div className="table-wrap" style={{ marginTop: ".75rem" }}>
              <table>
                <thead><tr><th>File</th><th>Document type</th><th>Progress</th><th><span className="sr-only">Remove</span></th></tr></thead>
                <tbody>
                  {picks.map((p) => (
                    <tr key={p.id}>
                      <td>{p.file.name} <span className="muted small">({formatBytes(p.file.size)})</span></td>
                      <td>
                        <label htmlFor={`dt-${p.id}`} style={{ position: "absolute", left: -999 }}>Document type for {p.file.name}</label>
                        <select id={`dt-${p.id}`} value={p.docType} disabled={submitting || p.done} onChange={(e) => setPicks((all) => all.map((x) => (x.id === p.id ? { ...x, docType: e.target.value } : x)))}>
                          {docOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                        </select>
                      </td>
                      <td>
                        {p.done ? <span className="badge outcome-no_issue_detected">Uploaded</span> :
                          p.error ? <span className="field-error">{p.error}</span> :
                          submitting ? <progress max={100} value={p.progress} aria-label={`Upload progress for ${p.file.name}`} /> : <span className="muted">Ready</span>}
                      </td>
                      <td>{!p.done && <button type="button" className="btn btn-small" disabled={submitting} onClick={() => setPicks((all) => all.filter((x) => x.id !== p.id))}>Remove</button>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </fieldset>
        {formError && <ErrorBox message={formError} />}
        <div className="page-actions">
          <button className="btn btn-primary" type="submit" disabled={submitting}>{submitting ? "Creating…" : createdId ? "Retry uploads" : "Create case"}</button>
          {createdId !== null && <Link className="btn" to={`/cases/${createdId}`}>Open the case</Link>}
          <Link className="btn" to="/cases">Cancel</Link>
        </div>
      </form>
    </div>
  );
}
