import sys, unittest
from datetime import date
sys.path.insert(0, ".")
from app.core.domain import (CaseData, ChecklistItem, DocumentData, EngineConfig, FieldData,
                             OUT_CONFIRM, OUT_ISSUE, OUT_NO_ISSUE, OUT_NOT_CHECKED)
from app.core.verification import run_verification

CHECKLIST = [
    ChecklistItem("fdr_scan", "FDR scan", True, ["fdr_number", "bank_name", "principal_amount", "currency", "issue_date", "maturity_date", "beneficiary_name"]),
    ChecklistItem("application_form", "Application form", True, ["principal_amount", "currency"]),
    ChecklistItem("authorisation_letter", "Authorisation letter", True, []),
]
TODAY = date(2026, 10, 24)


def doc(i, t, name=None, sha=None, st="processed"):
    return DocumentData(i, name or f"{t}.png", t, st, sha or f"sha{i}")


def fld(d, name, value, conf=95.0, status="extracted", page=1, needs=False, raw=None):
    return FieldData(d, name, value, raw or value, page, conf, status, needs)


def fdr_fields(d, **kw):
    base = dict(fdr_number="FDR-1", bank_name="Northwind Demo Bank Ltd", principal_amount="1000000.00", currency="INR",
                issue_date="2024-03-15", maturity_date="2026-03-15", beneficiary_name="Sample Institute")
    base.update(kw)
    return [fld(d, k, v) for k, v in base.items() if v is not None]


def form_fields(d, **kw):
    base = dict(principal_amount="1000000.00", currency="INR", fdr_number="FDR-1", beneficiary_name="Sample Institute")
    base.update(kw)
    return [fld(d, k, v) for k, v in base.items() if v is not None]


def run(docs, fields, case_type="refund", maturity=False, inst="", cfg=None):
    return run_verification(CaseData(case_type, inst, maturity, docs, fields), CHECKLIST, cfg, TODAY)


def by_rule(res, rule):
    return [f for f in res.findings if f.rule_id == rule]


def three_docs():
    return [doc(1, "fdr_scan", "fdr.png"), doc(2, "application_form", "form.png"), doc(3, "authorisation_letter", "auth.png")]


class MissingDocsAndFields(unittest.TestCase):
    def test_missing_document(self):
        res = run([doc(1, "fdr_scan"), doc(2, "application_form")], fdr_fields(1) + form_fields(2))
        miss = [f for f in by_rule(res, "DOC-MISSING") if f.outcome == OUT_ISSUE]
        self.assertEqual(len(miss), 1)
        self.assertIn("Authorisation letter", miss[0].title)
        self.assertTrue(miss[0].next_check)

    def test_missing_required_field_is_not_a_mismatch(self):
        res = run(three_docs(), fdr_fields(1, maturity_date=None) + form_fields(2))
        mf = [f for f in by_rule(res, "FIELD-MISSING") if f.outcome == OUT_ISSUE]
        self.assertEqual(len(mf), 1)
        self.assertEqual(mf[0].evidence[0].field_name, "maturity_date")
        self.assertNotIn(OUT_ISSUE, [f.outcome for f in by_rule(res, "CMP-MATURITY-DATE")])


class AmountAndCurrency(unittest.TestCase):
    def test_amount_mismatch_with_evidence(self):
        res = run(three_docs(), fdr_fields(1) + form_fields(2, principal_amount="100000.00"))
        a = [f for f in by_rule(res, "CMP-AMOUNT") if f.outcome == OUT_ISSUE]
        self.assertEqual(len(a), 1)
        f = a[0]
        self.assertEqual({e.value for e in f.evidence}, {"INR 1,000,000.00", "INR 100,000.00"})
        self.assertEqual({e.document_id for e in f.evidence}, {1, 2})
        self.assertEqual({e.filename for e in f.evidence}, {"fdr.png", "form.png"})
        self.assertIn("original FDR and the application form", f.next_check)
        self.assertEqual(res.overall_status, OUT_ISSUE)

    def test_matching_amounts_with_formatting_difference_not_flagged(self):
        # '1000000.00' vs same value: normalised decimals compare equal
        res = run(three_docs(), fdr_fields(1) + form_fields(2, principal_amount="1000000.00"))
        self.assertEqual([f.outcome for f in by_rule(res, "CMP-AMOUNT")], [OUT_NO_ISSUE])

    def test_matching_text_fields_with_formatting_not_flagged(self):
        res = run(three_docs(), fdr_fields(1, bank_name="STATE BANK OF INDIA LTD.", fdr_number="fdr-123 456",
                                           beneficiary_name="Sample  Institute")
                  + form_fields(2, fdr_number="FDR123456", beneficiary_name="SAMPLE INSTITUTE"))
        for rule in ("CMP-FDR-NUMBER", "CMP-BENEFICIARY"):
            self.assertEqual([f.outcome for f in by_rule(res, rule)], [OUT_NO_ISSUE], rule)

    def test_currency_mismatch_and_amounts_not_compared(self):
        res = run(three_docs(), fdr_fields(1) + form_fields(2, principal_amount="1000000.00", currency="USD"))
        self.assertEqual([f.outcome for f in by_rule(res, "CMP-CURRENCY")], [OUT_ISSUE])
        amt = by_rule(res, "CMP-AMOUNT")
        self.assertNotIn(OUT_ISSUE, [f.outcome for f in amt])
        self.assertIn(OUT_NOT_CHECKED, [f.outcome for f in amt])

    def test_amount_without_currency_never_compared(self):
        res = run(three_docs(), fdr_fields(1) + form_fields(2, principal_amount="100000.00", currency=None))
        amt = by_rule(res, "CMP-AMOUNT")
        self.assertNotIn(OUT_ISSUE, [f.outcome for f in amt])
        self.assertIn(OUT_CONFIRM, [f.outcome for f in amt])

    def test_fdr_number_and_bank_and_beneficiary_conflicts(self):
        res = run(three_docs(), fdr_fields(1) + form_fields(2, fdr_number="FDR-999", beneficiary_name="Other College"))
        self.assertEqual([f.outcome for f in by_rule(res, "CMP-FDR-NUMBER")], [OUT_ISSUE])
        self.assertEqual([f.outcome for f in by_rule(res, "CMP-BENEFICIARY")], [OUT_ISSUE])
        res = run(three_docs(), fdr_fields(1) + form_fields(2) + [fld(2, "bank_name", "Different Bank")])
        self.assertEqual([f.outcome for f in by_rule(res, "CMP-BANK")], [OUT_ISSUE])

    def test_unconfirmed_conflict_is_only_needs_confirmation(self):
        fields = fdr_fields(1) + [f for f in form_fields(2, principal_amount="100000.00")]
        for f in fields:
            if f.document_id == 2 and f.field_name == "principal_amount":
                f.confidence = 40.0
        res = run(three_docs(), fields)
        a = [f for f in by_rule(res, "CMP-AMOUNT")]
        self.assertEqual([f.outcome for f in a], [OUT_CONFIRM])

    def test_unconfirmed_text_conflicts_are_only_needs_confirmation(self):
        fields = fdr_fields(1) + form_fields(2, fdr_number="FDR-999", beneficiary_name="Other College")
        for f in fields:
            if f.document_id == 2 and f.field_name in ("fdr_number", "beneficiary_name"):
                f.confidence = 35.0
        res = run(three_docs(), fields)
        for rule in ("CMP-FDR-NUMBER", "CMP-BENEFICIARY"):
            self.assertEqual([f.outcome for f in by_rule(res, rule)], [OUT_CONFIRM], rule)

    def test_similar_looking_values_mention_possible_ocr_error(self):
        fields = fdr_fields(1, fdr_number="FDR-100234") + form_fields(2, fdr_number="FDR-1OO234")
        for f in fields:
            if f.document_id == 2 and f.field_name == "fdr_number":
                f.confidence = 50.0
        res = run(three_docs(), fields)
        f = by_rule(res, "CMP-FDR-NUMBER")[0]
        self.assertEqual(f.outcome, OUT_CONFIRM)
        self.assertIn("OCR", f.reason)

    def test_user_confirmed_text_conflict_becomes_issue(self):
        fields = fdr_fields(1) + form_fields(2, fdr_number="FDR-999")
        for f in fields:
            if f.document_id == 2 and f.field_name == "fdr_number":
                f.confidence, f.status = 35.0, "manual"
        res = run(three_docs(), fields)
        self.assertEqual([f.outcome for f in by_rule(res, "CMP-FDR-NUMBER")], [OUT_ISSUE])

    def test_user_confirmed_low_confidence_value_becomes_trusted(self):
        fields = fdr_fields(1) + form_fields(2, principal_amount="100000.00")
        for f in fields:
            if f.document_id == 2 and f.field_name == "principal_amount":
                f.confidence, f.status = 40.0, "confirmed"
        res = run(three_docs(), fields)
        self.assertEqual([f.outcome for f in by_rule(res, "CMP-AMOUNT")], [OUT_ISSUE])

    def test_single_document_comparison_not_checked(self):
        res = run([doc(1, "fdr_scan")], fdr_fields(1))
        self.assertEqual([f.outcome for f in by_rule(res, "CMP-AMOUNT")], [OUT_NOT_CHECKED])


class UncertainValues(unittest.TestCase):
    def test_unreadable_and_low_confidence_flagged(self):
        fields = fdr_fields(1) + form_fields(2)
        fields.append(FieldData(1, "branch", None, None, 2, None, "unreadable", True, "x"))
        for f in fields:
            if f.document_id == 1 and f.field_name == "bank_name":
                f.confidence = 50.0
        res = run(three_docs(), fields)
        u = by_rule(res, "FIELD-UNCONFIRMED")
        self.assertEqual([f.outcome for f in u], [OUT_CONFIRM])
        self.assertEqual({e.field_name for e in u[0].evidence}, {"branch", "bank_name"})
        self.assertEqual(res.overall_status, OUT_CONFIRM)

    def test_unreadable_value_not_used_in_comparison(self):
        fields = fdr_fields(1) + form_fields(2)
        fields = [f for f in fields if not (f.document_id == 2 and f.field_name == "principal_amount")]
        fields.append(FieldData(2, "principal_amount", None, "INR 1O0,000", 1, None, "unreadable", True))
        res = run(three_docs(), fields)
        self.assertNotIn(OUT_ISSUE, [f.outcome for f in by_rule(res, "CMP-AMOUNT")])

    def test_failed_ocr_document(self):
        docs = [doc(1, "fdr_scan", st="failed"), doc(2, "application_form"), doc(3, "authorisation_letter")]
        res = run(docs, form_fields(2))
        self.assertIn(OUT_CONFIRM, [f.outcome for f in by_rule(res, "DOC-PROCESSING")])

    def test_duplicate_files(self):
        docs = [doc(1, "fdr_scan", sha="same"), doc(2, "application_form", sha="same"), doc(3, "authorisation_letter")]
        res = run(docs, fdr_fields(1) + form_fields(2))
        self.assertIn(OUT_CONFIRM, [f.outcome for f in by_rule(res, "DOC-DUPLICATE")])


class Dates(unittest.TestCase):
    def test_invalid_date_order(self):
        res = run(three_docs(), fdr_fields(1, issue_date="2026-03-15", maturity_date="2024-03-15") + form_fields(2))
        o = by_rule(res, "DATE-ORDER")
        self.assertEqual([f.outcome for f in o], [OUT_ISSUE])
        self.assertEqual({e.field_name for e in o[0].evidence}, {"issue_date", "maturity_date"})

    def test_equal_dates_flagged(self):
        res = run(three_docs(), fdr_fields(1, issue_date="2025-01-01", maturity_date="2025-01-01") + form_fields(2))
        self.assertEqual([f.outcome for f in by_rule(res, "DATE-ORDER")], [OUT_ISSUE])

    def test_valid_order_not_flagged(self):
        res = run(three_docs(), fdr_fields(1) + form_fields(2))
        self.assertEqual([f.outcome for f in by_rule(res, "DATE-ORDER")], [OUT_NO_ISSUE])

    def test_maturity_passed_only_when_case_type_checks_it(self):
        res = run(three_docs(), fdr_fields(1) + form_fields(2), maturity=False)
        self.assertEqual([f.outcome for f in by_rule(res, "DATE-MATURITY")], [OUT_NOT_CHECKED])
        res = run(three_docs(), fdr_fields(1) + form_fields(2), maturity=True)
        self.assertEqual([f.outcome for f in by_rule(res, "DATE-MATURITY")], [OUT_ISSUE])

    def test_approaching_maturity(self):
        res = run(three_docs(), fdr_fields(1, maturity_date="2026-11-10") + form_fields(2), maturity=True)
        m = by_rule(res, "DATE-MATURITY")[0]
        self.assertEqual((m.outcome, m.severity), (OUT_ISSUE, "low"))
        self.assertIn("approaching", m.title.lower())

    def test_far_future_maturity_ok(self):
        res = run(three_docs(), fdr_fields(1, issue_date="2026-01-01", maturity_date="2028-01-01") + form_fields(2), maturity=True)
        self.assertEqual([f.outcome for f in by_rule(res, "DATE-MATURITY")], [OUT_NO_ISSUE])

    def test_conflicting_issue_dates(self):
        res = run(three_docs(), fdr_fields(1) + form_fields(2) + [fld(2, "issue_date", "2024-04-15")])
        self.assertEqual([f.outcome for f in by_rule(res, "CMP-ISSUE-DATE")], [OUT_ISSUE])

    def test_ambiguous_date_not_a_confirmed_issue(self):
        fields = fdr_fields(1, issue_date="2024-03-15") + form_fields(2)
        fields.append(FieldData(2, "issue_date", "05/06/2024", "05/06/2024", 1, 95.0, "extracted", True))
        res = run(three_docs(), fields)
        self.assertEqual([f.outcome for f in by_rule(res, "CMP-ISSUE-DATE")], [OUT_CONFIRM])


class CleanCaseAndLanguage(unittest.TestCase):
    def test_clean_case_has_no_issues_and_no_verified_language(self):
        res = run(three_docs(), fdr_fields(1) + form_fields(2) + [fld(3, "beneficiary_name", "Sample Institute")],
                  inst="Sample Institute")
        self.assertEqual(res.overall_status, OUT_NO_ISSUE)
        self.assertEqual(res.summary[OUT_ISSUE] + res.summary[OUT_CONFIRM], 0)
        text = " ".join(f.title + f.reason + f.next_check for f in res.findings).lower()
        for banned in ("verified genuine", "authenticated", "genuine fdr"):
            self.assertNotIn(banned, text)
        self.assertTrue(all(f.reason and f.next_check for f in res.findings))

    def test_institution_record_mismatch_is_only_a_prompt(self):
        res = run(three_docs(), fdr_fields(1) + form_fields(2), inst="Totally Different Trust")
        f = by_rule(res, "CMP-INSTITUTION-RECORD")
        self.assertEqual([x.outcome for x in f], [OUT_CONFIRM])

    def test_rules_version_and_timestamp(self):
        res = run(three_docs(), fdr_fields(1) + form_fields(2))
        self.assertTrue(res.rules_version)
        self.assertIsNotNone(res.generated_at)

    def test_every_finding_has_valid_outcome(self):
        res = run(three_docs(), fdr_fields(1) + form_fields(2, principal_amount="1.00"))
        valid = {OUT_ISSUE, OUT_CONFIRM, OUT_NOT_CHECKED, OUT_NO_ISSUE}
        self.assertTrue(all(f.outcome in valid for f in res.findings))

    def test_malformed_amount_value_does_not_crash(self):
        fields = fdr_fields(1) + form_fields(2, principal_amount="not-a-number")
        res = run(three_docs(), fields)
        self.assertNotIn(OUT_ISSUE, [f.outcome for f in by_rule(res, "CMP-AMOUNT")])

    def test_empty_case_does_not_crash(self):
        res = run([], [])
        self.assertTrue(any(f.outcome == OUT_ISSUE for f in res.findings))


if __name__ == "__main__":
    unittest.main()
