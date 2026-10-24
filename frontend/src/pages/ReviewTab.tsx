import { useState } from "react";
import { patch, post } from "../api";
import { ConfirmDialog, fmtDate, Notice, STATUS_LABEL, StatusBadge } from "../components/ui";
import { useCase } from "./CaseLayout";

type Target = "needs_review" | "awaiting_information" | "review_completed";
const TARGETS: { value: Target; label: string; help: string }[] = [
  { value: "needs_review", label: "Mark as Needs Review", help: "Reopen the case for review." },
  { value: "awaiting_information", label: "Mark as Awaiting Information", help: "Waiting for documents or answers from the institution." },
  { value: "review_completed", label: "Record Review Completed", help: "Records only that the human review step in this prototype is finished." },
];

export default function ReviewTab() {
  const { detail, reload } = useCase();
  const [notes, setNotes] = useState(detail.reviewer_notes ?? "");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ kind: "success" | "warn"; text: string } | null>(null);
  const [target, setTarget] = useState<Target | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  async function saveNotes() {
    setSaving(true);
    try { await patch(`/api/cases/${detail.id}`, { reviewer_notes: notes }); setMsg({ kind: "success", text: "Reviewer notes saved." }); reload(); }
    catch (e) { setMsg({ kind: "warn", text: e instanceof Error ? e.message : "Could not save notes." }); } finally { setSaving(false); }
  }
  async function confirm() {
    if (!target) return;
    setBusy(true);
    try {
      await post(`/api/cases/${detail.id}/status`, { status: target, note, confirm: true });
      setMsg({ kind: "success", text: `Status changed to ${STATUS_LABEL[target]}.` }); setTarget(null); setNote(""); reload();
    } catch (e) { setMsg({ kind: "warn", text: e instanceof Error ? e.message : "Could not change status." }); setTarget(null); }
    finally { setBusy(false); }
  }
  const completing = target === "review_completed";

  return (
    <div>
      <Notice kind="info">
        <strong>Human decision only.</strong> This tool never approves or rejects an FDR refund and never releases money. “Review Completed” only records that a person finished the review step here.
      </Notice>
      {msg && <Notice kind={msg.kind}>{msg.text}</Notice>}
      <h2>Current status</h2>
      <p><StatusBadge status={detail.status} /> {detail.analysis_stale && <span className="badge outcome-needs_confirmation">Analysis out of date</span>}</p>
      {detail.review_outcome && <p><strong>Recorded outcome note:</strong> {detail.review_outcome}</p>}
      <div className="page-actions">
        {TARGETS.map((t) => (
          <button key={t.value} className={`btn ${t.value === "review_completed" ? "btn-primary" : ""}`} disabled={detail.status === t.value}
                  title={t.help} onClick={() => { setTarget(t.value); setNote(""); }}>{t.label}</button>
        ))}
      </div>

      <h2>Reviewer notes</h2>
      <label htmlFor="rnotes" className="sr-only">Reviewer notes</label>
      <textarea id="rnotes" rows={5} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={5000} />
      <p><button className="btn" onClick={saveNotes} disabled={saving || notes === (detail.reviewer_notes ?? "")}>{saving ? "Saving…" : "Save notes"}</button></p>

      <h2>Status history</h2>
      <div className="table-wrap">
        <table>
          <thead><tr><th>When</th><th>Change</th><th>By</th><th>Note</th></tr></thead>
          <tbody>
            {[...detail.status_history].reverse().map((h) => (
              <tr key={h.id}><td>{fmtDate(h.created_at)}</td><td>{h.from_status ? `${STATUS_LABEL[h.from_status]} → ` : ""}{STATUS_LABEL[h.to_status]}</td><td>{h.actor}</td><td>{h.note ?? "—"}</td></tr>
            ))}
          </tbody>
        </table>
      </div>

      {target && (
        <ConfirmDialog title={TARGETS.find((t) => t.value === target)!.label} confirmLabel="Confirm" busy={busy}
                       disabled={completing && note.trim().length < 3} onConfirm={confirm} onCancel={() => setTarget(null)}>
          <p>{TARGETS.find((t) => t.value === target)!.help} This action is recorded in the audit history.</p>
          {completing && <p><strong>This is not an approval or rejection of a refund.</strong> The analysis must be current.</p>}
          <label htmlFor="snote">{completing ? "Review outcome note (required)" : "Note (optional)"}</label>
          <textarea id="snote" rows={3} value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} />
        </ConfirmDialog>
      )}
    </div>
  );
}
