import { useState } from "react";
import { Link } from "react-router-dom";
import { get } from "../api";
import { useAsync, useDebounced } from "../hooks";
import type { CaseSummary, Page } from "../types";
import { DemoBadge, Empty, ErrorBox, fmtDate, Loading, STATUS_LABEL, StatusBadge } from "./ui";

export function CaseBadges({ c }: { c: CaseSummary }) {
  return (
    <>
      <StatusBadge status={c.status} />
      {c.has_missing_documents && <span className="badge badge-missing">Missing Documents</span>}
      {c.has_discrepancies && <span className="badge outcome-issue_detected">Discrepancies</span>}
      {c.is_demo && <DemoBadge />}
    </>
  );
}

export default function CasesView({ pageSize, paginate }: { pageSize: number; paginate: boolean }) {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const dq = useDebounced(q);
  const { data, error, loading, reload } = useAsync(
    () => get<Page<CaseSummary>>(`/api/cases?page=${page}&page_size=${pageSize}&q=${encodeURIComponent(dq)}${status ? `&status=${status}` : ""}`),
    [dq, status, page, pageSize],
    (d) => (d?.items.some((c) => c.status === "processing") ? 2500 : null),
  );
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const filtered = Boolean(dq || status);

  return (
    <section aria-label="Cases">
      <div className="toolbar" role="search">
        <label className="sr-only" htmlFor="case-search" style={{ position: "absolute", left: -999 }}>Search cases</label>
        <input id="case-search" type="search" placeholder="Search by case ID, institution or reference" value={q}
               onChange={(e) => { setQ(e.target.value); setPage(1); }} />
        <label htmlFor="status-filter" style={{ position: "absolute", left: -999 }}>Filter by status</label>
        <select id="status-filter" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
          <option value="">All statuses</option>
          {Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
      {loading && !data && <Loading label="Loading cases…" />}
      {error && <ErrorBox message={error} onRetry={reload} />}
      {data && data.items.length === 0 && (
        <Empty title={filtered ? "No cases match your search or filter." : "No cases yet."}>
          {!filtered && <p>Create a case, or load the fictional demo cases from <Link to="/settings">Settings</Link>.</p>}
        </Empty>
      )}
      {data && data.items.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Case ID</th><th>Institution</th><th>Case type</th><th>Last updated</th><th>Status</th></tr></thead>
            <tbody>
              {data.items.map((c) => (
                <tr key={c.id}>
                  <td><Link to={`/cases/${c.id}`}>{c.case_code}</Link></td>
                  <td>{c.institution_name}</td>
                  <td>{c.case_type_name}</td>
                  <td>{fmtDate(c.updated_at)}</td>
                  <td><CaseBadges c={c} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {paginate && data && data.total > 0 && (
        <div className="pager">
          <button className="btn btn-small" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
          <span>Page {page} of {pages} · {data.total} case(s)</span>
          <button className="btn btn-small" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</button>
        </div>
      )}
    </section>
  );
}
