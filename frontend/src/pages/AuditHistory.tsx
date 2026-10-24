import { useState } from "react";
import { get } from "../api";
import AuditTable, { ACTION_LABEL } from "../components/AuditTable";
import { ErrorBox, Loading, Notice, PageHeader } from "../components/ui";
import { useAsync } from "../hooks";
import type { AuditEventOut, Page } from "../types";

export default function AuditHistory() {
  const [page, setPage] = useState(1);
  const [action, setAction] = useState("");
  const { data, error, loading, reload } = useAsync(() => get<Page<AuditEventOut>>(`/api/audit?page=${page}&page_size=50${action ? `&action=${action}` : ""}`), [page, action]);
  return (
    <div>
      <PageHeader title="Audit History" subtitle="Application-level events across all cases, newest first." />
      <Notice kind="info">This is application logging in a local database, <strong>not</strong> a tamper-proof regulatory audit system. The interface provides no way to edit or delete entries.</Notice>
      <div className="toolbar">
        <label htmlFor="act" className="sr-only">Filter by action</label>
        <select id="act" value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }}>
          <option value="">All actions</option>
          {Object.entries(ACTION_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
      {loading && !data && <Loading />}
      {error && <ErrorBox message={error} onRetry={reload} />}
      {data && <AuditTable data={data} page={page} setPage={setPage} showCase />}
    </div>
  );
}
