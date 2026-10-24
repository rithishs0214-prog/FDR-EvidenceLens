"""Runs the four demo scenarios through REAL Tesseract OCR + extraction + the verification engine
(no database or web framework involved)."""
import sys, unittest
from datetime import date
sys.path.insert(0, ".")
from app.core import ocr
from app.core.defaults import DEFAULT_CASE_TYPES
from app.core.domain import (CaseData, ChecklistItem, DocumentData, FieldData, OUT_CONFIRM, OUT_ISSUE, OUT_NO_ISSUE)
from app.core.extraction import extract_fields
from app.core.scenarios import build_scenarios
from app.core.verification import run_verification

CT = DEFAULT_CASE_TYPES[0]
CHECKLIST = [ChecklistItem(r["doc_type"], r["label"], r["required"], r["required_fields"]) for r in CT["rules"]]


def analyse(scn):
    docs, fields = [], []
    for i, d in enumerate(scn.documents, start=1):
        page = ocr.ocr_image(d.image, 1)
        docs.append(DocumentData(i, d.filename, d.doc_type, "processed", f"sha-{scn.key}-{i}"))
        for f in extract_fields([page]):
            fields.append(FieldData(i, f.field_name, f.value, f.raw_value, f.page_number, f.confidence,
                                    f.status, f.needs_confirmation, f.note))
    return run_verification(CaseData(CT["name"], scn.institution, False, docs, fields), CHECKLIST, today=date(2026, 10, 24))


@unittest.skipUnless(ocr.check_ocr_available()[0], "Tesseract not available")
class DemoScenarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = {s.key: analyse(s) for s in build_scenarios()}

    def rule(self, key, rule_id, outcome):
        return [f for f in self.res[key].findings if f.rule_id == rule_id and f.outcome == outcome]

    def test_A_missing_document(self):
        m = self.rule("A", "DOC-MISSING", OUT_ISSUE)
        self.assertEqual(len(m), 1)
        self.assertIn("Authorisation letter", m[0].title)
        self.assertEqual(self.res["A"].overall_status, OUT_ISSUE)

    def test_B_amount_conflict(self):
        f = self.rule("B", "CMP-AMOUNT", OUT_ISSUE)
        self.assertEqual(len(f), 1)
        self.assertEqual({e.value for e in f[0].evidence}, {"INR 1,000,000.00", "INR 100,000.00"})
        self.assertEqual({e.doc_type for e in f[0].evidence}, {"fdr_scan", "application_form"})
        self.assertTrue(all(e.page == 1 for e in f[0].evidence))

    def test_C_poor_quality_needs_confirmation(self):
        r = self.res["C"]
        flagged = self.rule("C", "FIELD-UNCONFIRMED", OUT_CONFIRM)
        missing = self.rule("C", "FIELD-MISSING", OUT_ISSUE)
        self.assertTrue(flagged or missing, "poor scan must produce unconfirmed or missing-field findings")
        self.assertNotEqual(r.overall_status, OUT_NO_ISSUE)
        # never a *confirmed* substantive amount/number conflict caused only by bad OCR
        self.assertFalse(self.rule("C", "CMP-AMOUNT", OUT_ISSUE))
        self.assertFalse(self.rule("C", "CMP-FDR-NUMBER", OUT_ISSUE))

    def test_D_no_discrepancies(self):
        r = self.res["D"]
        bad = [(f.rule_id, f.title) for f in r.findings if f.outcome in (OUT_ISSUE, OUT_CONFIRM)]
        self.assertEqual(bad, [])
        self.assertEqual(r.overall_status, OUT_NO_ISSUE)


if __name__ == "__main__":
    unittest.main()
