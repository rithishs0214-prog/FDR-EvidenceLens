import sys, unittest
from decimal import Decimal
sys.path.insert(0, ".")
from app.core.domain import OcrLine, OcrPage
from app.core.extraction import extract_fields
from app.core.normalize import (normalize_identifier, normalize_name, parse_amount, parse_date, parse_currency)


def page(*lines, conf=95.0, n=1):
    return OcrPage(n, "\n".join(lines), [OcrLine(l, conf) for l in lines], conf)


def get(fields, name):
    return next((f for f in fields if f.field_name == name), None)


class NormalizeTests(unittest.TestCase):
    def test_identifier_formatting_ignored(self):
        self.assertEqual(normalize_identifier("fdr-123 456"), normalize_identifier("FDR123456"))

    def test_name_formatting_ignored(self):
        self.assertEqual(normalize_name("The State Bank of India Ltd."), normalize_name("STATE BANK OF INDIA LIMITED"))
        self.assertNotEqual(normalize_name("Alpha Bank"), normalize_name("Beta Bank"))

    def test_amount_parsing(self):
        self.assertEqual(parse_amount("INR 1,000,000.00"), (Decimal("1000000.00"), "INR"))
        self.assertEqual(parse_amount("Rs. 10,00,000/-"), (Decimal("1000000.00"), "INR"))
        self.assertEqual(parse_amount("₹ 100000"), (Decimal("100000.00"), "INR"))
        self.assertEqual(parse_amount("5000"), (Decimal("5000.00"), None))

    def test_damaged_amount_not_guessed(self):
        self.assertIsNone(parse_amount("INR 1O0,000")[0])
        self.assertIsNone(parse_amount("INR abc")[0])

    def test_dates(self):
        self.assertEqual(parse_date("15 Mar 2024").value.isoformat(), "2024-03-15")
        self.assertEqual(parse_date("2024-03-15").value.isoformat(), "2024-03-15")
        self.assertEqual(parse_date("25/12/2024").value.isoformat(), "2024-12-25")
        a = parse_date("05/06/2025")
        self.assertTrue(a.ambiguous)
        self.assertFalse(parse_date("05/05/2025").ambiguous)
        self.assertIsNone(parse_date("31 Feb 2024").value)
        self.assertIsNone(parse_date("garbage").value)

    def test_currency(self):
        self.assertEqual(parse_currency("Rs."), "INR")
        self.assertEqual(parse_currency("usd"), "USD")


class ExtractionTests(unittest.TestCase):
    def test_extracts_all_fields(self):
        f = extract_fields([page(
            "FDR No: DEMO-FDR-100234", "Issuing Bank: Northwind Demo Bank Ltd", "Branch: Example Main Branch",
            "Principal Amount: INR 1,000,000.00", "Date of Issue: 15 Mar 2024", "Maturity Date: 15 Mar 2026",
            "Beneficiary: Sample Institute of Technology", "Status: Active")])
        self.assertEqual(get(f, "fdr_number").value, "DEMO-FDR-100234")
        self.assertEqual(get(f, "principal_amount").value, "1000000.00")
        self.assertEqual(get(f, "currency").value, "INR")
        self.assertEqual(get(f, "issue_date").value, "2024-03-15")
        self.assertEqual(get(f, "maturity_date").value, "2026-03-15")
        self.assertEqual(get(f, "bank_name").value, "Northwind Demo Bank Ltd")
        self.assertFalse(get(f, "principal_amount").needs_confirmation)
        self.assertEqual(get(f, "principal_amount").page_number, 1)

    def test_maturity_amount_not_mistaken_for_principal(self):
        f = extract_fields([page("Maturity Amount: INR 1,200,000.00")])
        self.assertIsNone(get(f, "principal_amount"))

    def test_low_confidence_needs_confirmation(self):
        f = extract_fields([page("FDR No: DEMO-FDR-100234", conf=55.0)])
        self.assertTrue(get(f, "fdr_number").needs_confirmation)

    def test_unreadable_amount_has_no_value(self):
        f = extract_fields([page("Principal Amount: INR 1O0,000")])
        a = get(f, "principal_amount")
        self.assertIsNone(a.value)
        self.assertEqual(a.status, "unreadable")
        self.assertTrue(a.needs_confirmation)

    def test_label_without_value_is_unreadable(self):
        a = get(extract_fields([page("Maturity Date:")]), "maturity_date")
        self.assertIsNone(a.value)
        self.assertTrue(a.needs_confirmation)

    def test_conflicting_values_on_one_document_not_guessed(self):
        f = extract_fields([page("FDR No: AAAA-1111", "Receipt No: BBBB-2222")])
        n = get(f, "fdr_number")
        self.assertIsNone(n.value)
        self.assertTrue(n.needs_confirmation)

    def test_repeated_same_value_ok(self):
        f = extract_fields([page("FDR No: AAAA-1111"), page("Receipt No: aaaa 1111", n=2)])
        self.assertEqual(get(f, "fdr_number").value, "AAAA-1111")

    def test_ambiguous_date_flagged(self):
        d = get(extract_fields([page("Date of Issue: 05/06/2025")]), "issue_date")
        self.assertTrue(d.needs_confirmation)
        self.assertIn("ambiguous", d.note.lower())

    def test_missing_currency_not_invented(self):
        f = extract_fields([page("Principal Amount: 100000")])
        self.assertIsNone(get(f, "currency"))
        self.assertEqual(get(f, "principal_amount").value, "100000.00")

    def test_currency_conflict_between_lines(self):
        f = extract_fields([page("Principal Amount: INR 100000", "Currency: USD")])
        self.assertIsNone(get(f, "currency").value)

    def test_bank_fallback_flagged(self):
        b = get(extract_fields([page("Northwind Demo Bank Ltd")]), "bank_name")
        self.assertTrue(b.needs_confirmation)


if __name__ == "__main__":
    unittest.main()
