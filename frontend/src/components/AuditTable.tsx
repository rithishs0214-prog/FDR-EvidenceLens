import { Link } from "react-router-dom";
import type { AuditEventOut, Page } from "../types";
import { Empty, fmtDate } from "./ui";

export const ACTION_LABEL: Record<string, string> = {
  case_created: "Case created", case_updated: "Case details updated", case_deleted: "Case deleted",
  document_uploaded: "Document uploaded", document_deleted: "Document deleted", ocr_retry: "OCR retried",
  field_corrected: "Field corrected", field_confirmed: "Field confirmed", analysis_run: "Analysis run",
  status_changed: "Status changed", reviewer_notes_updated: "Reviewer notes updated",
  checklist_rule_updated: "Checklist rule updated", case_type_updated: "Case type updated", demo_reset: "Demo data reset",
  login_success: "Login", login_failed: "Failed login attempt", logout: "Logout",
};

function details(e: AuditEventOut): string {
  return Object.entries(e.details).filter(([, v]) => v !== null && v !== undefined && v !== "")
    .map(([k, v]) => `${k.replace(/_/g, " ")}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`).join(" · ") || "—";
}

export default function AuditTable({ data, page, setPage, showCase }: { data: Page<AuditEventOut>; page: number; setPage: (p: number) => void; showCase: boolean }) {
  const pages = Math.max(1, Math.ceil(data.total / data.page_size));
  if (data.items.length === 0) return <Empty title="No events recorded yet." />;
  return (
    <>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Timestamp</th>{showCase && <th>Case</th>}<th>Action</th><th>By</th><th>Details</th></tr></thead>
          <tbody>
            {data.items.map((e) => (
              <tr key={e.id}>
                <td>{fmtDate(e.created_at)}</td>
                {showCase && <td>{e.case_id ? <Link to={`/cases/${e.case_id}`}>{e.case_code}</Link> : (e.case_code ?? "—")}</td>}
                <td>{ACTION_LABEL[e.action] ?? e.action}</td><td>{e.actor}</td><td className="small">{details(e)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="pager">
        <button className="btn btn-small" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
        <span>Page {page} of {pages} · {data.total} event(s)</span>
        <button className="btn btn-small" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</button>
      </div>
    </>
  );
}
