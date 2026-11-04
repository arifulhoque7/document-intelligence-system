"""REST API end to end (Celery eager, fake LLM): upload, status, results, corrections, search,
cross verification, reprocessing, settings and auth."""

import json
from decimal import Decimal

import pytest

from app.llm import LLMError
from devtools import synth


def upload(client, *files):
    r = client.post("/api/documents", files=[("files", (name, data, "application/octet-stream")) for name, data in files])
    assert r.status_code == 202, r.text
    return r.json()


@pytest.fixture
def truths(rng):
    return [synth.make_truth(rng, n_items=3, with_tax=True) for _ in range(3)]


# ---------- auth ----------

def test_requires_login(client):
    assert client.get("/api/documents").status_code == 401
    assert client.post("/api/auth/login", json={"email": "admin@example.com", "password": "wrong"}).status_code == 401


def test_login_rate_limited(client):
    for _ in range(10):
        client.post("/api/auth/login", json={"email": "x@example.com", "password": "bad"})
    assert client.post("/api/auth/login", json={"email": "x@example.com", "password": "bad"}).status_code == 429


def test_reviewer_cannot_touch_settings(admin):
    assert admin.post("/api/auth/users", json={"email": "rev@example.com", "password": "reviewer-123", "role": "reviewer"}).status_code == 201
    admin.post("/api/auth/logout")
    assert admin.post("/api/auth/login", json={"email": "rev@example.com", "password": "reviewer-123"}).status_code == 200
    assert admin.put("/api/settings/providers/openai", json={"api_key": "sk-x"}).status_code == 403
    assert admin.get("/api/documents").status_code == 200


def test_security_headers(admin):
    r = admin.get("/api/stats")
    assert r.headers["x-content-type-options"] == "nosniff" and "default-src 'none'" in r.headers["content-security-policy"]


# ---------- upload, processing, results ----------

def test_upload_many_types_and_process(admin, truths, tmp_path):
    synth.write_xlsx({"A": truths[:2], "B": truths[2:]}, tmp_path / "l.xlsx")
    synth.write_csv(truths[:1], tmp_path / "c.csv")
    res = upload(
        admin,
        ("one.pdf", synth.render_pdf([truths[0]])),
        ("bundle.pdf", synth.render_pdf(truths)),
        ("ledger.xlsx", (tmp_path / "l.xlsx").read_bytes()),
        ("export.csv", (tmp_path / "c.csv").read_bytes()),
        ("../../etc/passwd.pdf", b"not really a pdf"),
    )
    assert len(res["accepted"]) == 4
    assert res["rejected"][0]["filename"] == "passwd.pdf"  # path stripped, content rejected

    docs = {d["filename"]: d for d in admin.get("/api/documents").json()["items"]}
    assert docs["bundle.pdf"]["invoice_count"] == 3
    assert docs["ledger.xlsx"]["invoice_count"] == 3
    assert docs["passwd.pdf"]["status"] == "failed"

    detail = admin.get(f"/api/documents/{docs['one.pdf']['id']}").json()
    assert [e["stage"] for e in detail["events"]][:2] == ["queued", "processing"]
    assert detail["events"][-1]["stage"] == "done" and detail["progress"] == 100
    inv = detail["invoices"][0]
    for f in ("invoice_number", "invoice_date", "supplier_name", "customer_name", "total", "currency"):
        assert inv[f] == truths[0][f], f
    assert len(inv["line_items"]) == 3

    text = admin.get(f"/api/documents/{docs['one.pdf']['id']}/text").json()
    assert truths[0]["invoice_number"] in text[0]["text"]
    f = admin.get(f"/api/documents/{docs['one.pdf']['id']}/file")
    assert f.status_code == 200 and f.headers["content-disposition"].startswith("attachment")


def test_duplicate_invoice_flagged(admin, truths):
    pdf = synth.render_pdf([truths[0]])
    upload(admin, ("a.pdf", pdf))
    res = upload(admin, ("b.pdf", pdf))
    assert res["accepted"][0]["duplicate_of"]
    invs = admin.get("/api/invoices").json()["items"]
    assert any(i["code"] == "DUPLICATE_INVOICE" for inv in invs for i in inv["issues"])


def test_validation_flags_wrong_total_then_correction_clears_it(admin, truths):
    bad = {**truths[0], "total": str(Decimal(truths[0]["total"]) + 50)}
    upload(admin, ("bad.pdf", synth.render_pdf([bad])))
    inv = admin.get("/api/invoices", params={"needs_review": True}).json()["items"][0]
    assert "TOTAL_MISMATCH" in {i["code"] for i in inv["issues"]}
    assert inv["status"] == "needs_review"

    r = admin.patch(f"/api/invoices/{inv['id']}", json={"total": truths[0]["total"]})
    assert r.status_code == 200
    assert r.json()["changed"]["total"] == [bad["total"], truths[0]["total"]]
    assert "TOTAL_MISMATCH" not in {i["code"] for i in r.json()["invoice"]["issues"]}

    hist = admin.get(f"/api/invoices/{inv['id']}/history").json()
    assert [h["source"] for h in hist] == ["extraction", "manual"]
    assert admin.post(f"/api/invoices/{inv['id']}/approve").json()["status"] == "approved"
    assert admin.get(f"/api/documents/{inv['document_id']}").json()["status"] == "completed"


def test_correction_rejects_bad_input(admin, truths):
    upload(admin, ("a.pdf", synth.render_pdf([truths[0]])))
    inv_id = admin.get("/api/invoices").json()["items"][0]["id"]
    assert admin.patch(f"/api/invoices/{inv_id}", json={"currency": "XXX"}).status_code == 422
    assert admin.patch(f"/api/invoices/{inv_id}", json={"total": "abc"}).status_code == 422
    assert admin.patch(f"/api/invoices/{inv_id}", json={"is_admin": True}).status_code == 422


def test_keyword_filters(admin, truths):
    upload(admin, ("bundle.pdf", synth.render_pdf(truths)))
    t = truths[1]
    r = admin.get("/api/invoices", params={"supplier": t["supplier_name"][:6], "currency": t["currency"]}).json()
    assert t["invoice_number"] in {i["invoice_number"] for i in r["items"]}
    r = admin.get("/api/invoices", params={"invoice_number": t["invoice_number"]}).json()
    assert r["total"] == 1
    r = admin.get("/api/invoices", params={"min_total": t["total"], "max_total": t["total"]}).json()
    assert t["invoice_number"] in {i["invoice_number"] for i in r["items"]}
    assert admin.get("/api/invoices", params={"sort": "drop table"}).status_code == 422


@pytest.mark.parametrize("mode", ["keyword", "semantic", "hybrid"])
def test_search(admin, truths, mode):
    upload(admin, ("bundle.pdf", synth.render_pdf(truths)))
    t = truths[2]
    r = admin.get("/api/search", params={"q": f"{t['customer_name']} {t['line_items'][0]['description']}", "mode": mode})
    assert r.status_code == 200
    items = r.json()["items"]
    assert items and t["invoice_number"] in [i["invoice_number"] for i in items[:3]]


def test_semantic_search_without_embedding_provider(admin, fake_llm):
    fake_llm.embedding_enabled = False
    assert admin.get("/api/search", params={"q": "gloves", "mode": "semantic"}).status_code == 503
    assert admin.get("/api/search", params={"q": "gloves", "mode": "hybrid"}).status_code == 200


def test_cross_check_pdf_vs_excel(admin, truths, tmp_path):
    t = truths[0]
    synth.write_xlsx({"S": [{**t, "total": str(Decimal(t["total"]) + 100)}]}, tmp_path / "x.xlsx")
    upload(admin, ("inv.pdf", synth.render_pdf([t])))
    upload(admin, ("ledger.xlsx", (tmp_path / "x.xlsx").read_bytes()))
    checks = admin.get("/api/cross-checks").json()
    assert len(checks) == 1
    assert checks[0]["kind"] == "excel-pdf" and checks[0]["status"] == "mismatch" and "total" in checks[0]["differences"]
    # Both records are flagged, including the one processed first.
    for inv in admin.get("/api/invoices").json()["items"]:
        assert "CROSS_DOC_MISMATCH" in {i["code"] for i in inv["issues"]}


# ---------- failures and reprocessing ----------

def test_llm_failure_then_reprocess(admin, fake_llm, truths):
    fake_llm.fail_with = LLMError("Claude error 401: invalid x-api-key")
    upload(admin, ("a.pdf", synth.render_pdf([truths[0]])), ("b.pdf", synth.render_pdf([truths[1]])))
    docs = admin.get("/api/documents", params={"status": "failed"}).json()["items"]
    assert len(docs) == 2 and "401" in docs[0]["error"]

    fake_llm.fail_with = None
    assert len(admin.post("/api/documents/reprocess-failed").json()["requeued"]) == 2
    assert admin.get("/api/documents", params={"status": "failed"}).json()["total"] == 0
    doc = admin.get(f"/api/documents/{docs[0]['id']}").json()
    assert doc["attempts"] == 2 and doc["invoice_count"] == 1


def test_transient_llm_failure_gives_up_cleanly(admin, fake_llm, truths):
    fake_llm.fail_with = LLMError("Claude temporarily unavailable: 529", transient=True)
    doc_id = upload(admin, ("a.pdf", synth.render_pdf([truths[0]])))["accepted"][0]["id"]
    doc = admin.get(f"/api/documents/{doc_id}").json()
    assert doc["status"] == "failed" and "gave up" in doc["error"]
    assert admin.post(f"/api/documents/{doc_id}/reprocess").status_code == 202


def test_corrupted_and_oversized_uploads(admin, truths, monkeypatch):
    from app.core.config import get_settings

    pdf = synth.render_pdf([truths[0]])
    res = upload(admin, ("trunc.pdf", pdf[:400]), ("empty.pdf", b""))
    assert admin.get(f"/api/documents/{res['accepted'][0]['id']}").json()["status"] == "failed"
    assert res["rejected"][0]["reason"] == "File is empty"
    monkeypatch.setattr(get_settings(), "max_file_mb", 0)
    assert "exceeds" in upload(admin, ("big.pdf", pdf))["rejected"][0]["reason"]


def test_spreadsheet_needs_no_llm(admin, fake_llm, truths, tmp_path):
    fake_llm.fail_with = LLMError("should not be called")
    synth.write_csv(truths, tmp_path / "c.csv")
    upload(admin, ("c.csv", (tmp_path / "c.csv").read_bytes()))
    assert admin.get("/api/stats").json()["invoices"] == 3


# ---------- settings ----------

def test_provider_key_is_encrypted_and_masked(admin, db):
    from app.models import ProviderSetting

    r = admin.put("/api/settings/providers/openai", json={"api_key": "sk-proj-SECRETVALUE1234", "model": "gpt-5-mini"})
    assert r.status_code == 200 and r.json()["api_key_masked"] == "sk-…1234"
    assert "SECRETVALUE" not in json.dumps(admin.get("/api/settings/providers").json())
    assert "SECRETVALUE" not in db.get(ProviderSetting, "openai").api_key_enc
    assert admin.put("/api/settings/active", json={"llm": "openai", "embedding": "openai"}).status_code == 200
    active = {p["provider"]: p for p in admin.get("/api/settings/providers").json()}
    assert active["openai"]["active_llm"] and active["openai"]["active_embedding"]
    assert admin.put("/api/settings/active", json={"embedding": "claude"}).status_code == 422
    assert admin.put("/api/settings/providers/ollama", json={"base_url": "file:///etc/passwd"}).status_code == 422
    # Empty string removes the key.
    assert admin.put("/api/settings/providers/openai", json={"api_key": ""}).json()["has_key"] is False
