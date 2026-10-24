import { Link } from "react-router-dom";
import CasesView from "../components/CasesView";
import { Icon, PageHeader } from "../components/ui";

export default function Cases() {
  return (
    <div>
      <PageHeader title="Cases" subtitle="All cases, newest activity first.">
        <Link className="btn btn-primary" to="/cases/new"><Icon name="plus" /> Create New Case</Link>
      </PageHeader>
      <CasesView pageSize={20} paginate />
    </div>
  );
}
