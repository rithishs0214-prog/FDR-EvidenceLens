"""API / database integration tests. Require: pip install -r requirements-dev.txt  (run with pytest).
These were NOT executed in the authoring sandbox (FastAPI/SQLAlchemy/pytest could not be installed offline)."""
import dataclasses
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import models as m
from app.config import Settings
from app.core.auth import hash_password
from app.core import synthetic
from app.main import create_app

PNG = synthetic.to_png_bytes(Image.new("RGB", (300, 200), "white"))
REFUND = 1  # seeded "FDR Refund Review (demo checklist)"
WATCH = 2


def make_settings(tmp_path, **kw):
    base = dict(database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}", upload_dir=tmp_path / "uploads",
                max_upload_mb=1, app_env="development", enable_demo_endpoints=True)
    base.update(kw)
    return Settings(**base)


@pytest.fixture()
def settings(tmp_path):
    return make_settings(tmp_path)


USER, PASSWORD = "reviewer", "correct-horse-battery"


def add_user(client, username=USER, password=PASSWORD, active=True):
    with client.app.state.session_factory() as db:
        db.add(m.User(username=username, password_hash=hash_password(password, iterations=1000), is_active=active))
        db.commit()


def login(client, username=USER, password=PASSWORD):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def logged_in(client):
    add_user(client)
    assert login(client).status_code == 200
    return client


@pytest.fixture()
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield logged_in(c)


@pytest.fixture()
def anon(settings):
    """A client that is NOT logged in (a user exists)."""
    with TestClient(create_app(settings)) as c:
        add_user(c)
        yield c


def new_case(client, name="Sample Institute of Technology", case_type=REFUND, **kw):
    r = client.post("/api/cases", json={"institution_name": name, "case_type_id": case_type, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def upload(client, case_id, doc_type="fdr_scan", content=PNG, name="scan.png", mime="image/png"):
    return client.post(f"/api/cases/{case_id}/documents", data={"doc_type": doc_type}, files={"file": (name, content, mime)})


def doc(client, case_id, doc_type="fdr_scan", name="scan.png"):
    r = upload(client, case_id, doc_type, name=name)
    assert r.status_code == 201, r.text
    d = r.json()
    for _ in range(50):  # background OCR finishes quickly; wait defensively
        cur = client.get(f"/api/cases/{case_id}/documents/{d['id']}").json()
        if cur["processing_status"] in ("processed", "failed"):
            return cur
        time.sleep(0.1)
    return cur


def put(client, case_id, doc_id, **fields):
    for k, v in fields.items():
        r = client.put(f"/api/cases/{case_id}/documents/{doc_id}/fields/{k}", json={"value": v})
        assert r.status_code == 200, r.text


def analyse(client, case_id):
    r = client.post(f"/api/cases/{case_id}/analysis")
    assert r.status_code == 200, r.text
    return r.json()


def findings(res, rule, outcome=None):
    return [f for f in res["findings"] if f["rule_id"] == rule and (outcome is None or f["outcome"] == outcome)]


def two_doc_case(client, amount_a="1000000", amount_b="100000", cur_a="INR", cur_b="INR"):
    case = new_case(client)
    a = doc(client, case["id"], "fdr_scan", "fdr.png")
    b = doc(client, case["id"], "application_form", "form.png")
    put(client, case["id"], a["id"], principal_amount=amount_a, currency=cur_a, fdr_number="FDR-1001")
    put(client, case["id"], b["id"], principal_amount=amount_b, currency=cur_b, fdr_number="FDR-1001")
    return case, a, b


# ------------------------------------------------------------------ basics
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_case_creation_and_validation(client):
    c = new_case(client, name="  Sample   Institute ")
    assert c["institution_name"] == "Sample Institute" and c["case_code"].startswith("EL-") and c["status"] == "draft"
    assert client.post("/api/cases", json={"institution_name": "x", "case_type_id": REFUND}).status_code == 422
    assert client.post("/api/cases", json={"institution_name": "Valid Name", "case_type_id": 999}).status_code == 422
    assert client.post("/api/cases", json={"case_type_id": REFUND}).json()["error"]["code"] == "validation_error"
    assert client.get("/api/cases/9999").status_code == 404


def test_upload_rejections(client):
    cid = new_case(client)["id"]
    r = upload(client, cid, name="evil.exe", content=b"MZ", mime="application/octet-stream")
    assert r.status_code == 422 and r.json()["error"]["code"] == "unsupported_extension"
    r = upload(client, cid, name="fake.png", content=b"<html>not an image</html>", mime="image/png")
    assert r.status_code == 422 and r.json()["error"]["code"] == "content_mismatch"
    big = PNG + b"0" * (1024 * 1024 + 10)
    assert upload(client, cid, content=big).status_code == 413
    assert upload(client, cid, doc_type="not_a_type").status_code == 422


def test_successful_upload_uses_random_storage_name(client, settings):
    cid = new_case(client)["id"]
    d = doc(client, cid, name="../../secret name.png")
    assert d["original_filename"] == "secret name.png" and d["processing_status"] in ("processed", "failed")
    files = list(settings.upload_dir.iterdir())
    assert len(files) == 1 and "secret" not in files[0].name and files[0].suffix == ".png"
    r = client.get(f"/api/cases/{cid}/documents/{d['id']}/file")
    assert r.status_code == 200 and r.content == PNG and r.headers["x-content-type-options"] == "nosniff"
    assert "attachment" in client.get(f"/api/cases/{cid}/documents/{d['id']}/file?download=true").headers["content-disposition"]


def test_document_retrieval_isolated_between_cases(client):
    c1, c2 = new_case(client)["id"], new_case(client)["id"]
    d = doc(client, c1)
    assert client.get(f"/api/cases/{c1}/documents/{d['id']}/file").status_code == 200
    assert client.get(f"/api/cases/{c2}/documents/{d['id']}/file").status_code == 404
    assert client.get(f"/api/cases/{c2}/documents/{d['id']}").status_code == 404
    assert client.delete(f"/api/cases/{c2}/documents/{d['id']}?confirm=true").status_code == 404
    assert client.put(f"/api/cases/{c2}/documents/{d['id']}/fields/bank_name", json={"value": "X Bank"}).status_code == 404


# ------------------------------------------------------------------ verification through the API
def test_missing_required_documents(client):
    cid = new_case(client)["id"]
    doc(client, cid, "fdr_scan")
    res = analyse(client, cid)
    missing = findings(res, "DOC-MISSING", "issue_detected")
    assert {f["title"] for f in missing} == {"Missing document: Application form", "Missing document: Authorisation letter"}
    assert all(f["next_check"] and f["reason"] for f in res["findings"])
    assert any(c["doc_type"] == "fdr_scan" and c["present"] for c in res["checklist"])


def test_amount_mismatch_flagged_with_evidence(client):
    case, a, b = two_doc_case(client)
    res = analyse(client, case["id"])
    f = findings(res, "CMP-AMOUNT", "issue_detected")
    assert len(f) == 1
    assert {e["value"] for e in f[0]["evidence"]} == {"INR 1,000,000.00", "INR 100,000.00"}
    assert {e["document_id"] for e in f[0]["evidence"]} == {a["id"], b["id"]}
    assert {e["filename"] for e in f[0]["evidence"]} == {"fdr.png", "form.png"}
    assert "original FDR and the application form" in f[0]["next_check"]
    assert res["rules_version"] and res["last_analysis_at"] and res["stale"] is False


def test_matching_values_with_formatting_differences_not_flagged(client):
    case = new_case(client)
    a, b = doc(client, case["id"], "fdr_scan"), doc(client, case["id"], "application_form")
    put(client, case["id"], a["id"], bank_name="STATE BANK OF INDIA LTD.", principal_amount="INR 1,000,000", fdr_number="fdr-123 456")
    put(client, case["id"], b["id"], bank_name="State Bank of India Limited", principal_amount="Rs. 10,00,000/-", fdr_number="FDR123456")
    res = analyse(client, case["id"])
    for rule in ("CMP-BANK", "CMP-AMOUNT", "CMP-FDR-NUMBER"):
        assert not findings(res, rule, "issue_detected") and not findings(res, rule, "needs_confirmation"), rule
        assert findings(res, rule, "no_issue_detected"), rule


def test_currency_mismatch_not_compared_as_amounts(client):
    case, *_ = two_doc_case(client, amount_a="1000000", amount_b="1000000", cur_a="INR", cur_b="USD")
    res = analyse(client, case["id"])
    assert findings(res, "CMP-CURRENCY", "issue_detected")
    assert not findings(res, "CMP-AMOUNT", "issue_detected")


def test_unreadable_values_need_confirmation(client, settings):
    from app import models as m
    app = client.app
    case = new_case(client)
    d = doc(client, case["id"], "fdr_scan")
    with app.state.session_factory() as db:
        db.add(m.ExtractedFieldValue(case_id=case["id"], document_id=d["id"], field_name="maturity_date", value=None,
                                     raw_value="1O/O3/2026", status="unreadable", needs_confirmation=True,
                                     note="could not read"))
        db.add(m.ExtractedFieldValue(case_id=case["id"], document_id=d["id"], field_name="bank_name", value="Demo Bank",
                                     confidence=41.0, status="extracted", needs_confirmation=True))
        db.commit()
    res = analyse(client, case["id"])
    f = findings(res, "FIELD-UNCONFIRMED", "needs_confirmation")
    assert f and {e["field_name"] for e in f[0]["evidence"]} >= {"maturity_date", "bank_name"}
    names = {x["field_name"] for x in res["fields_needing_confirmation"]}
    assert {"maturity_date", "bank_name"} <= names
    assert res["overall_status"] in ("issue_detected", "needs_confirmation")


def test_invalid_date_order(client):
    case = new_case(client)
    a = doc(client, case["id"], "fdr_scan")
    put(client, case["id"], a["id"], issue_date="2026-01-01", maturity_date="2025-01-01")
    res = analyse(client, case["id"])
    f = findings(res, "DATE-ORDER", "issue_detected")
    assert len(f) == 1 and {e["field_name"] for e in f[0]["evidence"]} == {"issue_date", "maturity_date"}


def test_invalid_manual_values_rejected(client):
    case = new_case(client)
    a = doc(client, case["id"])
    base = f"/api/cases/{case['id']}/documents/{a['id']}/fields"
    assert client.put(f"{base}/principal_amount", json={"value": "abc"}).status_code == 422
    assert client.put(f"{base}/issue_date", json={"value": "05/06/2025"}).status_code == 422
    assert client.put(f"{base}/nonsense", json={"value": "x"}).status_code == 404
    assert client.put(f"{base}/bank_name", json={}).status_code == 422
    assert client.put(f"{base}/bank_name", json={"confirm": True}).status_code == 422  # nothing to confirm


def test_manual_correction_and_reanalysis(client):
    case, a, b = two_doc_case(client)
    assert findings(analyse(client, case["id"]), "CMP-AMOUNT", "issue_detected")
    put(client, case["id"], b["id"], principal_amount="1000000")
    assert client.get(f"/api/cases/{case['id']}/analysis").json()["stale"] is True
    res = analyse(client, case["id"])
    assert not findings(res, "CMP-AMOUNT", "issue_detected") and findings(res, "CMP-AMOUNT", "no_issue_detected")
    actions = [e["action"] for e in client.get(f"/api/cases/{case['id']}/audit").json()["items"]]
    assert "field_corrected" in actions and actions.count("analysis_run") == 2


# ------------------------------------------------------------------ review, audit, report
def test_status_changes_and_audit(client):
    cid = new_case(client)["id"]
    url = f"/api/cases/{cid}/status"
    assert client.post(url, json={"status": "awaiting_information"}).status_code == 400            # no confirm
    assert client.post(url, json={"status": "draft", "confirm": True}).status_code == 422            # not a human action
    assert client.post(url, json={"status": "review_completed", "confirm": True, "note": "ok done"}).status_code == 409  # no analysis
    r = client.post(url, json={"status": "awaiting_information", "confirm": True, "note": "Need letter"})
    assert r.status_code == 200 and r.json()["status"] == "awaiting_information"
    analyse(client, cid)
    assert client.post(url, json={"status": "review_completed", "confirm": True}).status_code == 422  # outcome note required
    r = client.post(url, json={"status": "review_completed", "confirm": True, "note": "Reviewed by human"})
    assert r.json()["status"] == "review_completed" and r.json()["review_outcome"] == "Reviewed by human"
    d = doc(client, cid)   # data change reopens a completed review
    assert client.get(f"/api/cases/{cid}").json()["status"] == "needs_review"
    events = client.get(f"/api/cases/{cid}/audit").json()["items"]
    actions = [e["action"] for e in events]
    for a in ("case_created", "document_uploaded", "analysis_run", "status_changed"):
        assert a in actions, a
    assert all(e["created_at"] and e["case_code"] for e in events)
    assert client.patch(f"/api/cases/{cid}", json={"reviewer_notes": "note"}).json()["reviewer_notes"] == "note"
    assert client.put(f"/api/audit/{events[0]['id']}", json={}).status_code in (404, 405)    # audit not editable
    assert client.delete(f"/api/audit/{events[0]['id']}").status_code in (404, 405)


def test_document_deletion_keeps_case(client, settings):
    cid = new_case(client)["id"]
    d = doc(client, cid)
    assert client.delete(f"/api/cases/{cid}/documents/{d['id']}").status_code == 400
    assert client.delete(f"/api/cases/{cid}/documents/{d['id']}?confirm=true").status_code == 204
    assert client.get(f"/api/cases/{cid}").status_code == 200
    assert list(settings.upload_dir.iterdir()) == []
    assert "document_deleted" in [e["action"] for e in client.get(f"/api/cases/{cid}/audit").json()["items"]]


def test_case_deletion_requires_confirmation_and_keeps_audit(client):
    cid = new_case(client)["id"]
    assert client.delete(f"/api/cases/{cid}").status_code == 400
    assert client.delete(f"/api/cases/{cid}?confirm=true").status_code == 204
    events = client.get("/api/audit", params={"action": "case_deleted"}).json()["items"]
    assert events and events[0]["case_id"] is None and events[0]["case_code"].startswith("EL-")


def test_retry_ocr(client):
    cid = new_case(client)["id"]
    d = doc(client, cid)
    r = client.post(f"/api/cases/{cid}/documents/{d['id']}/retry-ocr")
    assert r.status_code == 202


def test_report_contents(client):
    case, a, b = two_doc_case(client)
    analyse(client, case["id"])
    client.patch(f"/api/cases/{case['id']}", json={"reviewer_notes": "Checked originals"})
    r = client.get(f"/api/cases/{case['id']}/report")
    assert r.status_code == 200
    rep = r.json()
    assert rep["case_code"] == case["case_code"] and rep["institution_name"] == case["institution_name"]
    assert {d["filename"] for d in rep["documents"]} == {"fdr.png", "form.png"}
    assert any(f["field"] == "Principal amount" and f["confirmation"].startswith("Entered") for f in rep["fields"])
    assert any(f["rule_id"] == "CMP-AMOUNT" and f["outcome"] == "issue_detected" for f in rep["findings"])
    assert any(c["present"] is False for c in rep["checklist"])
    assert rep["next_checks"] and rep["rules_version"] and rep["reviewer_notes"] == "Checked originals"
    assert any("not an official AICTE system" in x for x in rep["limitations"])
    assert any("tamper-proof" in x for x in rep["limitations"])


# ------------------------------------------------------------------ dashboard, lists, rules
def test_dashboard_reflects_stored_data(client):
    assert client.get("/api/dashboard").json()["total_cases"] == 0
    case, *_ = two_doc_case(client)
    analyse(client, case["id"])
    new_case(client)
    d = client.get("/api/dashboard").json()
    assert d["total_cases"] == 2 and d["needs_review"] == 1
    assert d["missing_documents"] == 1 and d["unresolved_discrepancies"] == 1
    assert len(d["recent_cases"]) == 2


def test_list_search_filter_pagination(client):
    for n in ("Alpha College", "Beta University", "Gamma Institute"):
        new_case(client, name=n)
    r = client.get("/api/cases", params={"q": "beta"}).json()
    assert r["total"] == 1 and r["items"][0]["institution_name"] == "Beta University"
    r = client.get("/api/cases", params={"page_size": 2, "page": 2}).json()
    assert r["total"] == 3 and len(r["items"]) == 1
    assert client.get("/api/cases", params={"status": "needs_review"}).json()["total"] == 0
    assert client.get("/api/cases", params={"status": "bogus"}).status_code == 422
    assert client.get("/api/cases", params={"page_size": 1000}).status_code == 422


def test_checklist_rule_update_marks_cases_stale(client):
    case = new_case(client)
    analyse(client, case["id"])
    types = client.get("/api/case-types").json()
    rule = types[0]["rules"][1]
    r = client.put(f"/api/checklist-rules/{rule['id']}", json={"required": False})
    assert r.status_code == 200 and r.json()["required"] is False
    assert client.get(f"/api/cases/{case['id']}/analysis").json()["stale"] is True
    assert client.put(f"/api/checklist-rules/{rule['id']}", json={"required_fields": ["nope"]}).status_code == 422


# ------------------------------------------------------------------ demo protections
def test_demo_endpoints_blocked_outside_development(tmp_path):
    for i, kw in enumerate(({"app_env": "production"}, {"enable_demo_endpoints": False})):
        # https base URL: in production mode the session cookie is flagged Secure
        with TestClient(create_app(make_settings(tmp_path / f"case{i}", **kw)), base_url="https://testserver") as c:
            logged_in(c)
            assert c.post("/api/demo/seed").status_code == 403
            assert c.post("/api/demo/reset").status_code == 403


def test_demo_seed_and_reset_only_touch_demo_cases(client):
    user_case = new_case(client, name="My Real Case")
    r = client.post("/api/demo/seed")
    assert r.status_code == 200
    seeded = r.json()["cases"]
    assert [s["scenario"] for s in seeded] == ["A", "B", "C", "D"]
    cases = client.get("/api/cases", params={"page_size": 100}).json()["items"]
    assert sum(c["is_demo"] for c in cases) == 4
    again = client.post("/api/demo/seed").json()["cases"]            # repeatable, no duplicates
    assert len(client.get("/api/cases", params={"page_size": 100}).json()["items"]) == 5
    assert client.post("/api/demo/reset").json()["removed"] == 4
    left = client.get("/api/cases", params={"page_size": 100}).json()["items"]
    assert [c["id"] for c in left] == [user_case["id"]]


def test_demo_scenarios_use_real_engine(client):
    if not client.get("/api/health").json()["ocr_available"]:
        pytest.skip("Tesseract not installed")
    by = {s["scenario"]: s for s in client.post("/api/demo/seed").json()["cases"]}
    a = analyse(client, by["A"]["case_id"]); b = analyse(client, by["B"]["case_id"]); d = analyse(client, by["D"]["case_id"])
    assert findings(a, "DOC-MISSING", "issue_detected")
    assert findings(b, "CMP-AMOUNT", "issue_detected")
    assert d["overall_status"] == "no_issue_detected"
    c = analyse(client, by["C"]["case_id"])
    assert c["overall_status"] != "no_issue_detected"


# ------------------------------------------------------------------ authentication
PROTECTED = [("get", "/api/dashboard"), ("get", "/api/cases"), ("get", "/api/case-types"), ("get", "/api/config"),
             ("get", "/api/audit"), ("get", "/api/cases/1"), ("post", "/api/cases"), ("post", "/api/demo/seed"),
             ("get", "/api/cases/1/documents/1/file"), ("get", "/api/cases/1/report")]


def test_health_and_login_are_public_everything_else_is_protected(anon):
    assert anon.get("/api/health").status_code == 200
    for method, path in PROTECTED:
        r = getattr(anon, method)(path)
        assert r.status_code == 401, (method, path, r.status_code)
        assert r.json()["error"]["code"] in ("not_authenticated", "session_expired")
    assert anon.get("/api/auth/me").status_code == 401


def test_login_logout_flow(anon):
    r = login(anon)
    assert r.status_code == 200 and r.json() == {"username": USER, "display_name": None}
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "evidencelens_session=" in cookie
    assert PASSWORD not in r.text
    assert anon.get("/api/auth/me").json()["username"] == USER
    assert anon.get("/api/dashboard").status_code == 200
    assert anon.post("/api/auth/logout").status_code == 204
    assert anon.get("/api/dashboard").status_code == 401
    assert anon.post("/api/auth/logout").status_code == 204    # idempotent


def test_wrong_credentials_get_one_generic_message(anon):
    a = login(anon, password="not-the-password-1")
    b = login(anon, username="nobody-here", password="whatever-pass-1")
    assert a.status_code == b.status_code == 401
    assert a.json()["error"]["message"] == b.json()["error"]["message"]
    assert anon.get("/api/dashboard").status_code == 401


def test_inactive_user_cannot_log_in(settings):
    with TestClient(create_app(settings)) as c:
        add_user(c, active=False)
        assert login(c).status_code == 401


def test_login_is_throttled_after_repeated_failures(anon):
    for _ in range(5):
        assert login(anon, password="wrong-password-1").status_code == 401
    r = login(anon, password="wrong-password-1")
    assert r.status_code == 429 and r.json()["error"]["code"] == "too_many_attempts"
    assert login(anon).status_code == 429          # even the right password is refused while locked


def test_expired_session_is_rejected(anon):
    assert login(anon).status_code == 200
    from datetime import datetime, timedelta, timezone
    with anon.app.state.session_factory() as db:
        for s in db.query(m.AuthSession).all():
            s.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    r = anon.get("/api/dashboard")
    assert r.status_code == 401 and r.json()["error"]["code"] == "session_expired"


def test_password_and_token_are_not_stored_in_plain_text(anon):
    assert login(anon).status_code == 200
    token = anon.cookies.get("evidencelens_session")
    with anon.app.state.session_factory() as db:
        u = db.query(m.User).one()
        assert PASSWORD not in u.password_hash and u.password_hash.startswith("pbkdf2_sha256$")
        assert all(s.token_hash != token for s in db.query(m.AuthSession).all())


def test_auth_events_are_audited_without_secrets(anon):
    login(anon, password="wrong-password-1")
    login(anon)
    events = anon.get("/api/audit").json()["items"]
    actions = [e["action"] for e in events]
    assert "login_failed" in actions and "login_success" in actions
    assert "wrong-password-1" not in str(events) and PASSWORD not in str(events)
