"""Fictional demo scenarios. Every page is labelled as synthetic. Used by the demo seeder and tests."""
from __future__ import annotations

from dataclasses import dataclass, field

from . import synthetic as syn
from .defaults import DEMO_CASE_TYPE

INSTITUTION = "Sample Institute of Technology"
SYNTHETIC_TAG = "SYNTHETIC DEMO DATA"


@dataclass
class DemoDoc:
    doc_type: str
    filename: str
    image: object  # PIL image


@dataclass
class DemoScenario:
    key: str
    title: str
    description: str
    expected: str
    documents: list[DemoDoc] = field(default_factory=list)
    case_type_name: str = DEMO_CASE_TYPE
    institution: str = INSTITUTION


def _fdr(**kw):
    return DemoDoc("fdr_scan", "demo_fdr_scan.png", syn.render_document("FDR Receipt (fictional)", syn.fdr_scan_lines(**kw.pop("lines", {}), **{}), **kw))


def _form(**lines):
    return DemoDoc("application_form", "demo_application_form.png",
                   syn.render_document("Application Form (fictional)", syn.application_form_lines(**lines)))


def _letter():
    return DemoDoc("authorisation_letter", "demo_authorisation_letter.png",
                   syn.render_document("Authorisation Letter (fictional)", syn.authorisation_letter_lines()))


def build_scenarios() -> list[DemoScenario]:
    return [
        DemoScenario("A", "Missing supporting document",
                     "FDR scan and application form are consistent, but the authorisation letter was never supplied.",
                     "DOC-MISSING issue for the authorisation letter",
                     [_fdr(), _form()]),
        DemoScenario("B", "Conflicting FDR amount across two documents",
                     "The FDR scan shows INR 1,000,000.00 but the application form shows INR 100,000.00.",
                     "CMP-AMOUNT issue with both source values",
                     [_fdr(), _form(amount="INR 100,000.00"), _letter()]),
        DemoScenario("C", "Poor-quality document needing confirmation",
                     "The FDR scan is a low-quality image; values must be confirmed by a person before they are trusted.",
                     "Unreadable / unconfirmed values flagged",
                     [_fdr(degrade=2.5), _form(), _letter()]),
        DemoScenario("D", "No discrepancies detected by configured checks",
                     "All three documents are clean and agree with each other.",
                     "No issues detected by the configured rules",
                     [_fdr(), _form(), _letter()]),
    ]
