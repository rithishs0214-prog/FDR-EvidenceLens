import { useState } from "react";
import { get, post } from "../api";
import { ConfirmDialog, ErrorBox, Loading, Notice, PageHeader } from "../components/ui";
import { useAsync } from "../hooks";
import type { AppConfig, Health } from "../types";

interface SeedResult { cases: { scenario: string; title: string; case_code: string; overall_status: string; issues: number; needs_confirmation: number; expected: string }[] }

export default function Settings() {
  const cfg = useAsync(() => get<AppConfig>("/api/config"), []);
  const health = useAsync(() => get<Health>("/api/health"), []);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState<"seed" | "reset" | null>(null);
  const [msg, setMsg] = useState<{ kind: "success" | "warn"; text: string } | null>(null);
  const [seeded, setSeeded] = useState<SeedResult | null>(null);

  async function run() {
    if (!confirm) return;
    setBusy(true); setMsg(null);
    try {
      if (confirm === "seed") {
        const r = await post<SeedResult>("/api/demo/seed"); setSeeded(r);
        setMsg({ kind: "success", text: "Demo cases loaded. Open Cases to explore them." });
      } else {
        const r = await post<{ removed: number }>("/api/demo/reset"); setSeeded(null);
        setMsg({ kind: "success", text: `Removed ${r.removed} demo case(s). Your own cases were not touched.` });
      }
    } catch (e) { setMsg({ kind: "warn", text: e instanceof Error ? e.message : "Request failed." }); }
    finally { setBusy(false); setConfirm(null); }
  }

  if ((cfg.loading || health.loading) && !cfg.data) return <Loading />;
  if (cfg.error) return <ErrorBox message={cfg.error} onRetry={cfg.reload} />;
  const c = cfg.data!, h = health.data;
  return (
    <div>
      <PageHeader title="Settings" subtitle="Read-only status of this local installation. Change values in the .env file." />
      <Notice kind="warn">{c.notice}</Notice>
      <h2>System status</h2>
      <div className="table-wrap"><table><tbody>
        <tr><th>Environment</th><td>{c.environment}</td></tr>
        <tr><th>OCR (Tesseract program)</th><td>{h ? (h.ocr_available ? <span className="badge outcome-no_issue_detected">Available</span> : <span className="badge outcome-issue_detected">Unavailable</span>) : "…"} {h?.ocr_message}</td></tr>
        <tr><th>Supported uploads</th><td>{c.supported_formats}, up to {c.max_upload_mb} MB; PDFs up to {c.max_pdf_pages} pages</td></tr>
        <tr><th>OCR confidence threshold</th><td>{c.ocr_confidence_threshold}% (lower values need confirmation)</td></tr>
        <tr><th>Rules version</th><td>{c.rules_version}</td></tr>
      </tbody></table></div>

      <h2>Demonstration data</h2>
      <p className="muted">Loads four fictional cases (missing document, conflicting amount, poor-quality scan, no discrepancies). The documents are generated images labelled “SYNTHETIC DEMO DATA” and are processed by the same OCR and verification code as real uploads. Reset removes only demo cases.</p>
      {!c.demo_endpoints_enabled ? <Notice kind="info">Demo controls are disabled (they require APP_ENV=development and ENABLE_DEMO_ENDPOINTS=true).</Notice> : (
        <div className="page-actions">
          <button className="btn btn-primary" onClick={() => setConfirm("seed")}>Load / reload demo cases</button>
          <button className="btn" onClick={() => setConfirm("reset")}>Reset demo cases</button>
        </div>
      )}
      {msg && <Notice kind={msg.kind}>{msg.text}</Notice>}
      {seeded && (
        <div className="table-wrap"><table>
          <thead><tr><th>Scenario</th><th>Case</th><th>Intended demonstration</th><th>Result of analysis</th></tr></thead>
          <tbody>{seeded.cases.map((s) => <tr key={s.scenario}><td>{s.scenario}. {s.title}</td><td>{s.case_code}</td><td>{s.expected}</td><td>{s.overall_status.replace(/_/g, " ")} ({s.issues} issue(s), {s.needs_confirmation} to confirm)</td></tr>)}</tbody>
        </table></div>
      )}

      <h2>Privacy and limitations</h2>
      <ul>
        <li>Basic username/password login only (no roles, no MFA, no password reset): every logged-in user sees every case. Use synthetic data only.</li>
        <li>Uploaded files are stored in a private folder outside the web root and served only through the case-scoped endpoint.</li>
        <li>The audit history is application-level logging, not a tamper-proof regulatory audit trail.</li>
        <li>Results never authenticate an FDR or decide a refund. See the README for the work needed before real-world use.</li>
      </ul>

      {confirm && (
        <ConfirmDialog title={confirm === "seed" ? "Load demo cases?" : "Reset demo cases?"} confirmLabel={confirm === "seed" ? "Load demo cases" : "Reset demo cases"}
                       busy={busy} danger={confirm === "reset"} onConfirm={run} onCancel={() => setConfirm(null)}>
          <p>{confirm === "seed" ? "Existing demo cases are replaced by four fresh ones. This can take around half a minute while OCR runs." : "All cases marked SYNTHETIC DEMO DATA and their files will be deleted. Cases you created yourself are not affected."}</p>
        </ConfirmDialog>
      )}
    </div>
  );
}
