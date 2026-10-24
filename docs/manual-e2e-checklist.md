# Manual end-to-end checklist (create case → print report)

Prerequisite: backend on :8000, frontend on :5173, `python -m app.cli init-db` done. Use fictional documents only
(or the generated demo documents). Tick each box only after you have seen the result.

1. [ ] Dashboard opens with 0 cases (or only demo cases); metrics match the case table; empty state is shown when empty.
2. [ ] **New Case**: submit empty → inline errors; enter institution name + case type; drop in a `.exe` → rejected message; a >10 MB file → rejected.
3. [ ] Choose two fictional PNG/PDF files (FDR scan + application form), set types, submit → progress bars, case page opens, no double-submit if you click twice.
4. [ ] **Documents & fields**: status goes Queued/Processing → Processed (or Failed with a clear OCR setup message if Tesseract is missing).
5. [ ] *View* opens the file in a new tab; *Download* downloads it; the URL of a document from another case returns an error.
6. [ ] *Fields*: values show OCR confidence and page; low-confidence ones show "Needs confirmation"; edit one value → Save → shows "Entered by reviewer".
7. [ ] Try an invalid value (amount `abc`, date `05/06/2025`) → clear validation message, nothing saved.
8. [ ] *Retry OCR* on a document works; *Remove* shows a confirmation dialog, then removes only that document.
9. [ ] **Verification results**: "Run analysis" → checklist, findings grouped by outcome, side-by-side evidence (file, page, value), reason and next check; timestamp + rules version shown.
10. [ ] Make the amounts differ (e.g. INR 1,000,000 vs INR 100,000) → "Conflicting principal amounts" with both documents listed.
11. [ ] Correct one amount → results show "out of date" banner → rerun → conflict disappears.
12. [ ] **Review**: change status without confirming is impossible (dialog); "Record Review Completed" demands a note and a current analysis.
13. [ ] **History**: events for creation, upload, field correction, analysis, status change, deletion; Audit History page shows them across cases.
14. [ ] **Report**: contents complete; *Print / Save as PDF* → A4 preview without sidebar, readable; limitations section present; demo cases carry the SYNTHETIC banner.
15. [ ] Dashboard counts changed accordingly. Settings → load demo cases (four scenarios) → reset demo cases → your own case is still there.
16. [ ] Stop Tesseract (rename/unset `TESSERACT_CMD`) → upload still works, shows a setup message, manual entry still possible.
17. [ ] Resize to phone width: menu button works, tables scroll sideways, dialogs usable; Tab key reaches every control with a visible focus ring.
