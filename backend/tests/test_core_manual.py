import sys, unittest
sys.path.insert(0, ".")
from app.core.manual import ManualValueError, normalize_manual_value as n


class ManualTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(n("principal_amount", "INR 1,000,000"), ("1000000.00", "INR 1,000,000", "INR"))
        self.assertEqual(n("issue_date", "2025-03-15")[0], "2025-03-15")
        self.assertEqual(n("issue_date", "15 Mar 2025")[0], "2025-03-15")
        self.assertEqual(n("currency", "inr")[0], "INR")
        self.assertEqual(n("bank_name", "  Demo   Bank ")[0], "Demo Bank")

    def test_invalid(self):
        for f, v in [("principal_amount", "1O0"), ("principal_amount", "-5"), ("issue_date", "05/06/2025"),
                     ("issue_date", "nonsense"), ("currency", "rupees"), ("fdr_number", "!!"), ("bank_name", "  "),
                     ("not_a_field", "x")]:
            with self.assertRaises(ManualValueError, msg=f"{f}={v}"):
                n(f, v)


if __name__ == "__main__":
    unittest.main()
