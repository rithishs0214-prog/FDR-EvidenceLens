import { ReactNode, useEffect, useRef } from "react";
import type { CaseStatus, Outcome } from "../types";

export const STATUS_LABEL: Record<string, string> = {
  draft: "Draft", processing: "Processing", needs_review: "Needs Review",
  awaiting_information: "Awaiting Information", review_completed: "Review Completed",
};
export const OUTCOME_LABEL: Record<Outcome, string> = {
  issue_detected: "Issue detected", needs_confirmation: "Needs confirmation",
  not_checked: "Not checked", no_issue_detected: "No issue detected by configured rules",
};

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

const ICONS: Record<string, string> = {
  dashboard: "M3 3h8v8H3zM13 3h8v5h-8zM13 10h8v11h-8zM3 13h8v8H3z",
  cases: "M4 4h16v4H4zM4 10h16v4H4zM4 16h16v4H4z",
  plus: "M12 5v14M5 12h14",
  rules: "M9 11l3 3 8-8M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h9",
  audit: "M12 8v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z",
  settings: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19 12a7 7 0 0 0-.1-1.2l2-1.5-2-3.4-2.3.9a7 7 0 0 0-2-1.2L14.2 3h-4l-.4 2.6a7 7 0 0 0-2 1.2l-2.3-.9-2 3.4 2 1.5a7 7 0 0 0 0 2.4l-2 1.5 2 3.4 2.3-.9a7 7 0 0 0 2 1.2l.4 2.6h4l.4-2.6a7 7 0 0 0 2-1.2l2.3.9 2-3.4-2-1.5c.1-.4.1-.8.1-1.2z",
  menu: "M4 6h16M4 12h16M4 18h16",
  print: "M6 9V3h12v6M6 18H4v-7h16v7h-2M6 14h12v7H6z",
  refresh: "M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7",
  trash: "M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13",
  eye: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  upload: "M12 16V4M7 9l5-5 5 5M4 20h16",
};

export function Icon({ name }: { name: string }) {
  return (
    <svg className="icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d={ICONS[name] ?? ""} />
    </svg>
  );
}

export function StatusBadge({ status }: { status: CaseStatus | string }) {
  return <span className={`badge badge-${status}`}>{STATUS_LABEL[status] ?? status}</span>;
}
export function OutcomeBadge({ outcome }: { outcome: Outcome }) {
  return <span className={`badge outcome-${outcome}`}>{OUTCOME_LABEL[outcome]}</span>;
}
export function DemoBadge() {
  return <span className="badge badge-demo">SYNTHETIC DEMO DATA</span>;
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return <div className="state" role="status" aria-live="polite"><span className="spinner" aria-hidden="true" /> {label}</div>;
}
export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="alert alert-error" role="alert">
      <strong>Something needs attention.</strong> {message}
      {onRetry && <> <button className="btn btn-small" onClick={onRetry}>Try again</button></>}
    </div>
  );
}
export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return <div className="state empty"><p><strong>{title}</strong></p>{children}</div>;
}
export function Notice({ kind = "info", children }: { kind?: "info" | "warn" | "success"; children: ReactNode }) {
  return <div className={`alert alert-${kind}`} role={kind === "warn" ? "alert" : "status"}>{children}</div>;
}
export function PageHeader({ title, children, subtitle }: { title: string; subtitle?: string; children?: ReactNode }) {
  return (
    <header className="page-header">
      <div><h1>{title}</h1>{subtitle && <p className="muted">{subtitle}</p>}</div>
      <div className="page-actions">{children}</div>
    </header>
  );
}

export function ConfirmDialog(props: {
  title: string; children: ReactNode; confirmLabel: string; danger?: boolean; busy?: boolean; disabled?: boolean;
  onConfirm: () => void; onCancel: () => void;
}) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    cancelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") props.onCancel(); };
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); prev?.focus?.(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) props.onCancel(); }}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="dlg-title">
        <h2 id="dlg-title">{props.title}</h2>
        <div className="modal-body">{props.children}</div>
        <div className="modal-actions">
          <button ref={cancelRef} className="btn" onClick={props.onCancel} disabled={props.busy}>Cancel</button>
          <button className={`btn ${props.danger ? "btn-danger" : "btn-primary"}`} onClick={props.onConfirm}
                  disabled={props.busy || props.disabled}>{props.busy ? "Working…" : props.confirmLabel}</button>
        </div>
      </div>
    </div>
  );
}

export function formatBytes(n: number): string {
  return n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`;
}
