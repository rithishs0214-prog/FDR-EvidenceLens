import { useState } from "react";
import { get } from "../api";
import AuditTable from "../components/AuditTable";
import { ErrorBox, Loading, Notice } from "../components/ui";
import { useAsync } from "../hooks";
import type { AuditEventOut, Page } from "../types";
import { useCase } from "./CaseLayout";

export default function HistoryTab() {
  const { detail } = useCase();
  const [page, setPage] = useState(1);
  const { data, error, loading, reload } = useAsync(() => get<Page<AuditEventOut>>(`/api/cases/${detail.id}/audit?page=${page}&page_size=25`), [detail.id, detail.updated_at, page]);
  return (
    <div>
      <Notice kind="info">This history is application-level logging in a local database. It is <strong>not</strong> a tamper-proof regulatory audit trail, although the interface offers no way to edit or delete entries.</Notice>
      {loading && <Loading />}
      {error && <ErrorBox message={error} onRetry={reload} />}
      {data && <AuditTable data={data} page={page} setPage={setPage} showCase={false} />}
    </div>
  );
}
