import { Link, NavLink, Outlet, useOutletContext, useParams } from "react-router-dom";
import { get } from "../api";
import { CaseBadges } from "../components/CasesView";
import { ErrorBox, Loading, Notice } from "../components/ui";
import { useAsync } from "../hooks";
import type { CaseDetail } from "../types";

export interface CaseCtx { detail: CaseDetail; reload: () => void }
export const useCase = () => useOutletContext<CaseCtx>();

export default function CaseLayout() {
  const { caseId } = useParams();
  const { data, error, loading, reload } = useAsync(
    () => get<CaseDetail>(`/api/cases/${caseId}`),
    [caseId],
    (d) => (d?.documents.some((x) => x.processing_status === "pending" || x.processing_status === "processing") ? 2000 : null),
  );
  if (loading && !data) return <Loading label="Loading case…" />;
  if (error && !data) return <div><ErrorBox message={error} onRetry={reload} /><p><Link to="/cases">Back to cases</Link></p></div>;
  if (!data) return null;
  const tab = ({ isActive }: { isActive: boolean }) => `tab ${isActive ? "active" : ""}`;
  return (
    <div>
      <p className="muted small no-print"><Link to="/cases">Cases</Link> / {data.case_code}</p>
      <header className="page-header">
        <div>
          <h1>{data.institution_name}</h1>
          <p className="muted">{data.case_code} · {data.case_type_name}{data.application_ref ? ` · Ref ${data.application_ref}` : ""}</p>
        </div>
        <div><CaseBadges c={data} /></div>
      </header>
      {data.is_demo && <Notice kind="warn"><strong>SYNTHETIC DEMO DATA.</strong> This case uses fictional documents created for demonstration.</Notice>}
      {error && <ErrorBox message={error} onRetry={reload} />}
      <nav className="tabs" aria-label="Case sections">
        <NavLink to={`/cases/${data.id}`} end className={tab}>Documents &amp; fields</NavLink>
        <NavLink to={`/cases/${data.id}/results`} className={tab}>Verification results</NavLink>
        <NavLink to={`/cases/${data.id}/review`} className={tab}>Review</NavLink>
        <NavLink to={`/cases/${data.id}/history`} className={tab}>History</NavLink>
        <NavLink to={`/cases/${data.id}/report`} className={tab}>Report</NavLink>
      </nav>
      <Outlet context={{ detail: data, reload } satisfies CaseCtx} />
    </div>
  );
}
