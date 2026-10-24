import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth";
import { Loading } from "./components/ui";
import Login from "./pages/Login";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Cases from "./pages/Cases";
import NewCase from "./pages/NewCase";
import CaseLayout from "./pages/CaseLayout";
import DocumentsTab from "./pages/DocumentsTab";
import ResultsTab from "./pages/ResultsTab";
import ReviewTab from "./pages/ReviewTab";
import HistoryTab from "./pages/HistoryTab";
import Report from "./pages/Report";
import Rules from "./pages/Rules";
import AuditHistory from "./pages/AuditHistory";
import Settings from "./pages/Settings";

/** Everything except /login needs a logged-in user; otherwise go to the login page and come back after. */
function RequireAuth() {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <div style={{ padding: "2rem" }}><Loading label="Checking your session…" /></div>;
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname + loc.search }} />;
  return <Layout />;
}

function NotFound() {
  return <div className="page"><h1>Page not found</h1><p><Link to="/">Back to the dashboard</Link></p></div>;
}

export default function App() {
  return (
    <Routes>
      <Route path="login" element={<Login />} />
      <Route element={<RequireAuth />}>
        <Route index element={<Dashboard />} />
        <Route path="cases" element={<Cases />} />
        <Route path="cases/new" element={<NewCase />} />
        <Route path="cases/:caseId" element={<CaseLayout />}>
          <Route index element={<DocumentsTab />} />
          <Route path="results" element={<ResultsTab />} />
          <Route path="review" element={<ReviewTab />} />
          <Route path="history" element={<HistoryTab />} />
          <Route path="report" element={<Report />} />
        </Route>
        <Route path="rules" element={<Rules />} />
        <Route path="audit" element={<AuditHistory />} />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
