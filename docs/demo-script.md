# Demo script for SIH judges (~6 minutes)

**Setup (before the demo):** backend + frontend running, Tesseract installed, Settings → *Load demo cases*.

1. **Framing (30 s).** "FDR EvidenceLens is a reviewer's assistant, not an approver. It never contacts a bank or decides a refund; it shows *why* something needs a human look." Point at the banner and the Dashboard — numbers come from stored cases.
2. **Scenario B — conflicting amount (90 s).** Open the case → *Verification results*. Show the *Conflicting principal amounts* finding: INR 1,000,000.00 on the FDR scan vs INR 100,000.00 on the application form, with file, page, OCR confidence, the reason and the suggested next check. Open *View* to show the real image.
3. **Scenario C — poor scan (60 s).** Show "Values requiring confirmation": unreadable or low-confidence fields are *never silently trusted*. Open *Documents & fields*, confirm one value and correct another, rerun analysis; the findings update.
4. **Scenario A — missing document (30 s).** Checklist shows *Authorisation letter — Missing*. Mention the checklist is configurable and clearly a demo list (Rules / Checklist page).
5. **Scenario D — clean case (30 s).** "No issue detected by configured rules" — deliberately not "verified genuine".
6. **Live upload (90 s).** New Case → upload a fictional PNG/PDF → watch Processing → Processed → edit a value → run analysis.
7. **Human review + audit (45 s).** Review tab: confirmation dialog, outcome note, "Review Completed" ≠ approval. History tab and Audit History show every action.
8. **Report (30 s).** Report tab → Print / Save as PDF (A4), limitations section.
9. **Honest limits (30 s).** Local single-user prototype, no authentication, no bank integration, OCR is imperfect, checklist is a demonstration. Mention the engine is a framework-free module with automated tests.

**Backup plan:** if OCR misbehaves on stage, use manual entry on any uploaded document — the comparison engine and evidence display work identically.
