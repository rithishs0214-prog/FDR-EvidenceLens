import { Link } from "react-router-dom";
import { get } from "../api";
import CasesView from "../components/CasesView";
import { ErrorBox, Icon, Loading, PageHeader } from "../components/ui";
import { useAsync } from "../hooks";
import type { DashboardOut } from "../types";

export default function Dashboard() {
  const { data, error, loading, reload } = useAsync(() => get<DashboardOut>("/api/dashboard"), []);
  return (
    <div>
      <PageHeader title="Dashboard" subtitle="Metrics are calculated from the cases stored in the database.">
        <Link className="btn btn-primary" to="/cases/new"><Icon name="plus" /> Create New Case</Link>
      </PageHeader>
      {loading && <Loading />}
      {error && <ErrorBox message={error} onRetry={reload} />}
      {data && (
        <div className="cards">
          <Link className="card metric" to="/cases"><div className="num">{data.total_cases}</div><div className="lbl">Total cases</div></Link>
          <Link className="card metric" to="/cases"><div className="num">{data.needs_review}</div><div className="lbl">Cases needing review</div></Link>
          <div className="card metric"><div className="num">{data.missing_documents}</div><div className="lbl">Cases with missing documents</div></div>
          <div className="card metric"><div className="num">{data.unresolved_discrepancies}</div><div className="lbl">Cases with unresolved discrepancies</div></div>
        </div>
      )}
      <p className="muted small">“Missing documents” and “discrepancies” count cases whose latest analysis found such an issue. Re-run a case’s analysis to refresh it.</p>
      <h2>Recent cases</h2>
      <CasesView pageSize={8} paginate={false} />
      <p><Link to="/cases">View all cases</Link></p>
    </div>
  );
}
