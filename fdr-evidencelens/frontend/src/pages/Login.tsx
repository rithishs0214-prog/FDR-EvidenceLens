import { CSSProperties, FormEvent, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import "../login.css";

const d = (ms: number) => ({ "--d": `${ms}ms` } as CSSProperties);

export default function Login() {
  const { user, loading, login } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const raw = (loc.state as { from?: string } | null)?.from;
  const from = raw && raw.startsWith("/") && !raw.startsWith("//") && raw !== "/login" ? raw : "/";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!loading && user) return <Navigate to={from} replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    if (!username.trim() || !password) { setError("Enter your username and password."); return; }
    setBusy(true); setError(null);
    try {
      await login(username.trim(), password);
      nav(from, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not log in. Please try again.");
      setPassword("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="lg-page">
      <header className="lg-nav">
        <div className="lg-brand"><span className="lg-mark" aria-hidden="true">◎</span> FDR EvidenceLens</div>
        <span className="lg-chip">Prototype · decision support only</span>
      </header>

      <main className="lg-grid">
        <section className="lg-hero" aria-labelledby="lg-title">
          <p className="lg-eyebrow lg-rise" style={d(0)}><span className="lg-eyebrow-dot" aria-hidden="true" /> FDR DOCUMENT REVIEW</p>
          <h1 id="lg-title" className="lg-rise" style={d(100)}>Review FDR documents with the evidence in front of you</h1>
          <p className="lg-lead lg-rise" style={d(200)}>
            Upload the papers, see what does not match and why, and record your own decision.
            EvidenceLens suggests; the reviewer decides.
          </p>
          <ul className="lg-points">
            <li className="lg-rise" style={d(320)}><b>Evidence for every finding</b><span>File, page and value shown side by side</span></li>
            <li className="lg-rise" style={d(420)}><b>Honest about uncertainty</b><span>Unclear scans are flagged, never guessed</span></li>
            <li className="lg-rise" style={d(520)}><b>Human decision, full history</b><span>Nothing is approved automatically</span></li>
          </ul>
        </section>

        <section className="lg-visual" aria-hidden="true">
          <div className="lg-scene">
            <span className="lg-blob lg-blob-1" /><span className="lg-blob lg-blob-2" />
            <div className="lg-doc lg-doc-a">
              <div className="lg-doc-head"><span>FDR scan</span><em>fictional sample</em></div>
              <div className="lg-row"><span>FDR No</span><b>SAMPLE-558201</b></div>
              <div className="lg-row"><span>Bank</span><b>Northwind Demo Bank</b></div>
              <div className="lg-row lg-hl"><span>Principal</span><b>INR 500,000.00</b></div>
              <div className="lg-row"><span>Maturity</span><b>10 Jan 2027</b></div>
              <span className="lg-scanline" />
            </div>
            <div className="lg-doc lg-doc-b">
              <div className="lg-doc-head"><span>Application form</span><em>fictional sample</em></div>
              <div className="lg-row"><span>FDR No</span><b>SAMPLE-558201</b></div>
              <div className="lg-row lg-hl lg-hl-late"><span>Amount</span><b>INR 50,000.00</b></div>
            </div>
            <div className="lg-flag"><span className="lg-pulse" /> Amount differs between 2 documents</div>
            <div className="lg-evidence">
              <p className="lg-evidence-title">Evidence-linked findings</p>
              <ul>
                <li><i>✓</i> Source file and page shown</li>
                <li><i>✓</i> Reason and next check suggested</li>
                <li><i>✓</i> Reviewer confirms every decision</li>
              </ul>
            </div>
          </div>
        </section>

        <section className="lg-panel" aria-labelledby="lg-form-title">
          <form onSubmit={submit} noValidate aria-busy={busy} className="lg-form">
            <h2 id="lg-form-title" className="lg-rise" style={d(150)}>Log in to EvidenceLens</h2>
            <p className="lg-sub lg-rise" style={d(230)}>Reviewer access to the document review workspace.</p>

            {error && <div className="lg-error" role="alert">{error}</div>}

            <div className="lg-field lg-rise" style={d(300)}>
              <label htmlFor="lg-user">USERNAME</label>
              <input id="lg-user" type="text" autoComplete="username" autoFocus spellCheck={false} autoCapitalize="none"
                     placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)}
                     aria-invalid={!!error} maxLength={100} />
            </div>
            <div className="lg-field lg-rise" style={d(380)}>
              <label htmlFor="lg-pass">PASSWORD</label>
              <div className="lg-pass">
                <input id="lg-pass" type={show ? "text" : "password"} autoComplete="current-password" placeholder="Password"
                       value={password} onChange={(e) => setPassword(e.target.value)} aria-invalid={!!error} maxLength={200} />
                <button type="button" className="lg-toggle" onClick={() => setShow(!show)} aria-pressed={show}
                        aria-label={show ? "Hide password" : "Show password"}>{show ? "Hide" : "Show"}</button>
              </div>
            </div>

            <button className="lg-submit lg-rise" style={d(460)} type="submit" disabled={busy}>
              {busy ? "Signing in…" : <>Log In <span className="lg-arrow" aria-hidden="true">→</span></>}
            </button>

            <p className="lg-help lg-rise" style={d(540)}>
              No account yet? On the computer running the backend, create one with<br />
              <code>python -m app.cli create-user --username your-name</code>
            </p>
          </form>
          <p className="lg-fine">Local demo with a basic login (no roles, no MFA). Use fictional documents only.</p>
        </section>
      </main>
    </div>
  );
}
