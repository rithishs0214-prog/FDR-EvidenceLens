"""Seeded DEMONSTRATION checklist. These are NOT official requirements of any institution or of
AICTE; they exist so the prototype has something to evaluate. Edit them under Rules / Checklist."""
from __future__ import annotations

DOC_TYPE_LABELS = {
    "fdr_scan": "FDR / receipt scan",
    "application_form": "Application form",
    "authorisation_letter": "Authorisation letter",
    "other": "Other supporting document",
}
DEMO_CASE_TYPE = "FDR Refund Review (demo checklist)"
WATCH_CASE_TYPE = "FDR Maturity Watch (demo checklist)"

_FDR_FIELDS = ["fdr_number", "bank_name", "principal_amount", "currency", "issue_date", "maturity_date", "beneficiary_name"]

DEFAULT_CASE_TYPES = [
    {
        "name": DEMO_CASE_TYPE,
        "description": "Demonstration checklist (not an official requirement list): FDR scan, application form and authorisation letter.",
        "check_maturity": False,
        "rules": [
            {"doc_type": "fdr_scan", "label": DOC_TYPE_LABELS["fdr_scan"], "required": True, "required_fields": _FDR_FIELDS},
            {"doc_type": "application_form", "label": DOC_TYPE_LABELS["application_form"], "required": True,
             "required_fields": ["fdr_number", "principal_amount", "currency", "beneficiary_name"]},
            {"doc_type": "authorisation_letter", "label": DOC_TYPE_LABELS["authorisation_letter"], "required": True,
             "required_fields": ["beneficiary_name"]},
        ],
    },
    {
        "name": WATCH_CASE_TYPE,
        "description": "Demonstration checklist that also checks expired / approaching maturity dates.",
        "check_maturity": True,
        "rules": [
            {"doc_type": "fdr_scan", "label": DOC_TYPE_LABELS["fdr_scan"], "required": True, "required_fields": _FDR_FIELDS},
            {"doc_type": "application_form", "label": DOC_TYPE_LABELS["application_form"], "required": False,
             "required_fields": ["fdr_number", "principal_amount", "currency"]},
        ],
    },
]
