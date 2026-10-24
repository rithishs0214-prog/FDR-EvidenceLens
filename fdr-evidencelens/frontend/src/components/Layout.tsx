import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { Icon } from "./ui";

const NAV = [
  { to: "/", label: "Dashboard", icon: "dashboard", end: true },
  { to: "/cases", label: "Cases", icon: "cases", end: true },
  { to: "/cases/new", label: "New Case", icon: "plus", end: true },
  { to: "/rules", label: "Rules / Checklist", icon: "rules", end: true },
  { to: "/audit", label: "Audit History", icon: "audit", end: true },
  { to: "/settings", label: "Settings", icon: "settings", end: true },
];

export default function Layout() {
  const [open, setOpen] = useState(false);
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  async function signOut() { await logout(); navigate("/login", { replace: true }); }
  return (
    <div className="shell">
      <a className="skip-link" href="#main">Skip to main content</a>
      <aside id="primary-nav" className={`sidebar ${open ? "open" : ""}`} aria-label="Primary">
        <div className="brand"><span className="brand-mark" aria-hidden="true">◎</span> FDR EvidenceLens</div>
        <nav>
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} onClick={() => setOpen(false)}
                     className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
              <Icon name={n.icon} /> <span>{n.label}</span>
            </NavLink>
          ))}
        </nav>
        <p className="sidebar-note">Prototype decision-support tool. Not an official AICTE system.</p>
      </aside>
      <div className="content">
        <div className="topbar">
          <button className="btn menu-btn" aria-expanded={open} aria-controls="primary-nav" onClick={() => setOpen(!open)}>
            <Icon name="menu" /> Menu
          </button>
          <span className="topbar-note">Local demo · basic login · synthetic data only</span>
          <span style={{ marginLeft: "auto" }}>Signed in as <strong>{user?.display_name || user?.username}</strong></span>
          <button className="btn btn-small" onClick={signOut}>Log out</button>
        </div>
        <main id="main" tabIndex={-1}><Outlet /></main>
      </div>
    </div>
  );
}
