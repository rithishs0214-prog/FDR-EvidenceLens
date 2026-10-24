import { useState } from "react";
import { get, patch, put } from "../api";
import { ErrorBox, Loading, Notice, PageHeader } from "../components/ui";
import { useAsync } from "../hooks";
import type { AppConfig, CaseTypeOut, RuleOut } from "../types";

function RuleEditor({ rule, fieldLabels, onSaved }: { rule: RuleOut; fieldLabels: Record<string, string>; onSaved: () => void }) {
  const [label, setLabel] = useState(rule.label);
  const [required, setRequired] = useState(rule.required);
  const [fields, setFields] = useState<string[]>(rule.required_fields);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  async function save() {
    setBusy(true); setMsg(null);
    try { await put(`/api/checklist-rules/${rule.id}`, { label, required, required_fields: fields }); setMsg({ ok: true, text: "Saved. Cases of this type need their analysis rerun." }); onSaved(); }
    catch (e) { setMsg({ ok: false, text: e instanceof Error ? e.message : "Could not save." }); } finally { setBusy(false); }
  }
  const toggle = (f: string) => setFields((cur) => (cur.includes(f) ? cur.filter((x) => x !== f) : [...cur, f]));
  return (
    <div className="card" style={{ marginBottom: ".75rem" }}>
      <div className="row" style={{ marginBottom: ".5rem" }}>
        <div><label htmlFor={`l-${rule.id}`}>Document name <span className="hint">({rule.doc_type})</span></label>
          <input id={`l-${rule.id}`} type="text" value={label} onChange={(e) => setLabel(e.target.value)} maxLength={200} /></div>
        <div><label htmlFor={`r-${rule.id}`}>Requirement</label>
          <select id={`r-${rule.id}`} value={required ? "yes" : "no"} onChange={(e) => setRequired(e.target.value === "yes")}>
            <option value="yes">Required</option><option value="no">Optional</option></select></div>
      </div>
      <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
        <legend><strong>Fields that must be present on this document</strong></legend>
        <div className="checks">
          {Object.entries(fieldLabels).map(([k, v]) => (
            <label key={k}><input type="checkbox" checked={fields.includes(k)} onChange={() => toggle(k)} /> {v}</label>
          ))}
        </div>
      </fieldset>
      <p><button className="btn btn-small" onClick={save} disabled={busy || label.trim().length < 2}>{busy ? "Saving…" : "Save rule"}</button>
        {msg && <span className={msg.ok ? "muted" : "field-error"} role="status"> {msg.text}</span>}</p>
    </div>
  );
}

export default function Rules() {
  const types = useAsync(() => get<CaseTypeOut[]>("/api/case-types"), []);
  const cfg = useAsync(() => get<AppConfig>("/api/config"), []);
  const [err, setErr] = useState<string | null>(null);
  async function setMaturity(id: number, v: boolean) {
    setErr(null);
    try { await patch(`/api/case-types/${id}`, { check_maturity: v }); types.reload(); }
    catch (e) { setErr(e instanceof Error ? e.message : "Could not update."); }
  }
  if (types.loading && !types.data) return <Loading />;
  if (types.error) return <ErrorBox message={types.error} onRetry={types.reload} />;
  return (
    <div>
      <PageHeader title="Rules / Checklist" subtitle="Configurable document checklists per case type." />
      <Notice kind="warn"><strong>Demonstration checklist.</strong> These requirements were invented for the prototype. They are not the official requirements of any bank, institution or AICTE. Replace them with requirements you have confirmed.</Notice>
      <p className="muted">Comparison rules (FDR number, amount and currency, bank, institution name, dates) are built into the backend rules engine (version {cfg.data?.rules_version ?? "…"}); OCR values below {cfg.data?.ocr_confidence_threshold ?? 80}% confidence always need confirmation.</p>
      {err && <ErrorBox message={err} />}
      {types.data?.map((t) => (
        <section key={t.id}>
          <h2>{t.name}</h2>
          <p className="muted">{t.description}</p>
          <label className="checks" style={{ fontWeight: 400 }}>
            <span><input type="checkbox" checked={t.check_maturity} onChange={(e) => setMaturity(t.id, e.target.checked)} /> Check for passed / approaching maturity dates (window: {cfg.data?.approaching_maturity_days ?? 30} days)</span>
          </label>
          {t.rules.map((r) => <RuleEditor key={`${r.id}-${r.label}-${r.required}-${r.required_fields.join()}`} rule={r} fieldLabels={cfg.data?.field_labels ?? {}} onSaved={types.reload} />)}
        </section>
      ))}
    </div>
  );
}
