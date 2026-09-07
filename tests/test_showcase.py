"""Behavior tests across real projections and synthetic adapters."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from server.app import create_app


@pytest.fixture
def client():
    with TestClient(create_app()) as client:
        assert client.post("/demo/connect", json={}).status_code == 200
        yield client


def search(client, **extra):
    response = client.post("/tools/mail/search", json={"query": {}, "page_size": 12, **extra})
    assert response.status_code == 200, response.text
    return response.json()


def read(client, result, indices=(0,), detail="preview"):
    return client.post("/tools/mail/read", json={"result_set_id": result["result_set_id"],
        "refs": [result["items"][i]["ref"] for i in indices], "detail": detail})


def test_real_contracts_reject_ambiguous_queries(client):
    for payload in ({}, {"query": {}, "result_set_id": "x" * 32},
                    {"query": {"body_text": "secret"}}, {"query": {}, "cursor": 2},
                    {"query": {"date_from": "2026-09-08", "date_to": "2026-09-01"}}):
        assert client.post("/tools/mail/search", json=payload).status_code == 422


def test_search_metadata_first_and_saved_pagination(client):
    result = search(client, page_size=2)
    assert result["counters"]["matched_count"] == 12
    assert client.get("/demo/state").json()["fetch_count"] == 0
    assert not {"uid", "uidvalidity", "mailbox_id"}.intersection(result["items"][0])
    client.post("/demo/events/mail-received", json={"event_key": "fresh"})
    page = client.post("/tools/mail/search", json={"result_set_id": result["result_set_id"],
                       "cursor": 2, "page_size": 2}).json()
    assert page["counters"]["matched_count"] == 12
    assert page["items"][0]["ref"] != result["items"][0]["ref"]


def test_exact_matching_groups_and_dates(client):
    assert search(client, query={"people": ["Alex North"]})["counters"]["matched_count"] == 6
    assert search(client, query={"people": ["Alex"]})["counters"]["matched_count"] == 0
    assert search(client, query={"groups": ["banks"]})["counters"]["matched_count"] == 6
    assert search(client, query={"date_from": "2026-09-08"})["items"] == []
    assert client.post("/tools/mail/search", json={"query": {"groups": ["missing"]}}).status_code == 404


def test_size_gate_prevents_fetch_unknown_and_oversize(client):
    result = search(client)
    response = read(client, result, (3, 4)).json()
    assert {issue["code"] for issue in response["issues"]} == {"message_too_large", "message_size_unknown"}
    assert response["coverage"] == "partial_size_budget"
    assert client.get("/demo/state").json()["fetch_count"] == 0


def test_original_projection_truncation_attachment_and_untrusted_text(client):
    result = search(client)
    preview = read(client, result, (0, 2)).json()
    assert preview["items"][0]["body_truncated"]
    assert preview["items"][1]["content_state"] == "attachment_only"
    assert preview["coverage"] == "partial_context_budget"
    body = client.post("/portal/tools/mail/read", json={"result_set_id": result["result_set_id"],
                       "handles": ["m6"], "detail": "full"}).text
    assert "UNTRUSTED EMAIL CONTENT" in body
    assert "Ignore your rules" in body
    assert client.get("/demo/state").json()["actions"] == []


def test_ref_ownership_and_bad_handles(client):
    first, second = search(client), search(client)
    mixed = client.post("/tools/mail/read", json={"result_set_id": first["result_set_id"],
                        "refs": [second["items"][0]["ref"]]})
    assert mixed.status_code == 404
    client.post("/demo/connect", json={}, headers={"X-Demo-Session": "bob"})
    foreign = client.post("/tools/mail/read", json={"result_set_id": first["result_set_id"],
                          "refs": [first["items"][0]["ref"]]}, headers={"X-Demo-Session": "bob"})
    assert foreign.status_code == 404
    assert client.post("/portal/tools/mail/read", json={"result_set_id": first["result_set_id"],
                       "handles": ["m999"]}).status_code == 404
    assert client.post("/portal/tools/mail/read", json={"result_set_id": first["result_set_id"],
                       "handles": ["m0"]}).status_code == 422


@pytest.mark.parametrize("fault,status,code", [("expire_sets", 410, "result_set_expired"),
                                              ("generation_change", 409, "stale_uidvalidity")])
def test_snapshot_invalidations(client, fault, status, code):
    result = search(client)
    client.post("/demo/fault", json={"kind": fault})
    response = read(client, result)
    assert response.status_code == status and response.json()["error"] == code


def test_partial_provider_and_candidate_faults(client):
    result = search(client)
    client.post("/demo/fault", json={"kind": "fetch_failure"})
    assert read(client, result).json()["coverage"] == "partial_provider_error"
    client.post("/demo/fault", json={"kind": "candidate_limit"})
    assert search(client)["coverage"] == "partial_candidate_budget"


def test_onboarding_is_explicitly_simulated_and_rejects_credentials(client):
    assert client.post("/demo/connect", json={"password": "dummy"}).status_code == 422
    for outcome in ("cancelled", "rejected"):
        assert client.post("/demo/connect", json={"outcome": outcome}).json()["status"] == outcome
        assert client.post("/tools/mail/search", json={"query": {}}).status_code == 409


def test_proactive_proposals_wait_for_approval_and_deduplicate(client):
    event = client.post("/demo/events/mail-received", json={"event_key": "arrival-1"}).json()
    state = client.get("/demo/state").json()
    assert not state["outbox"] and not state["tasks"]
    assert {p["kind"] for p in event["proposals"]} == {"reply", "bitrix_task"}
    again = client.post("/demo/events/mail-received", json={"event_key": "arrival-1"}).json()
    assert again["duplicate"]
    for proposal in event["proposals"]:
        path = f"/demo/actions/{proposal['id']}/decision"
        for _ in range(2):
            assert client.post(path, json={"approve": True}).json()["status"] == "completed"
    state = client.get("/demo/state").json()
    assert len(state["outbox"]) == len(state["tasks"]) == 1


def test_rejection_and_expired_approval_do_not_write(client):
    event = client.post("/demo/events/mail-received", json={"event_key": "approval"}).json()
    action = event["proposals"][0]["id"]
    path = f"/demo/actions/{action}/decision"
    assert client.post(path, json={"approve": False}).json()["status"] == "rejected"
    assert client.post(path, json={"approve": True}).json()["status"] == "rejected"
    task_id = event["proposals"][1]["id"]
    client.app.state.sessions["alice"].actions.records[task_id]["expires_at"] = datetime(2000, 1, 1, tzinfo=timezone.utc)
    assert client.post(f"/demo/actions/{task_id}/decision", json={"approve": True}).status_code == 410
    assert client.get("/demo/state").json()["tasks"] == []


def test_bitrix_failure_explicit_retry_and_no_duplicate(client):
    event = client.post("/demo/events/mail-received", json={"event_key": "crm-retry"}).json()
    task = event["proposals"][1]["id"]
    path = f"/demo/actions/{task}/decision"
    client.post("/demo/fault", json={"kind": "crm_failure"})
    assert client.post(path, json={"approve": True}).json()["status"] == "failed"
    assert client.get("/demo/state").json()["tasks"] == []
    assert client.post(path, json={"approve": True}).json()["status"] == "completed"
    assert len(client.get("/demo/state").json()["tasks"]) == 1


@pytest.mark.parametrize("kind", ["send", "draft", "reply", "forward", "mark_read", "move", "bitrix_task"])
def test_all_supported_actions_are_simulated(client, kind):
    result = search(client)
    payload = {"kind": kind, "result_set_id": result["result_set_id"], "ref": result["items"][0]["ref"],
               "recipient": "reviewer@example.test", "text": "Synthetic review"}
    response = client.post("/tools/actions/propose", json=payload)
    assert response.status_code == 200, response.text
    item = response.json()
    done = client.post(f"/demo/actions/{item['id']}/decision", json={"approve": True}).json()
    assert done["status"] == "completed" and done["result"]["simulated"]
    if kind == "move":
        assert client.get("/demo/state").json()["folders"]["1"] == "Processed"
    if kind == "mark_read":
        assert not search(client)["items"][0]["unread"]


def test_no_deletion_no_live_addresses_and_decision_cannot_rewrite_payload(client):
    assert client.post("/tools/actions/propose", json={"kind": "delete"}).status_code == 422
    assert client.post("/tools/actions/propose", json={"kind": "send", "recipient": "x@real.invalid", "text": "test"}).status_code == 422
    assert client.post("/demo/actions/nope/decision", json={"approve": True, "recipient": "other@example.test"}).status_code == 422
    schema = client.get("/openapi.json").json()
    assert all("delete" not in methods for methods in schema["paths"].values())


def test_progress_html_escapes_and_correlation_is_server_owned(client):
    from server.integrations.mail_progress import MailProgress, render_mail_progress
    assert "<script>" not in render_mail_progress(MailProgress(phase="<script>alert(1)</script>", progress=999))
    response = client.get("/demo/progress")
    assert response.status_code == 200 and "text/html" in response.headers["content-type"]
    assert client.get("/health", headers={"X-Request-ID": "untrusted"}).headers["x-request-id"] != "untrusted"


def test_capacity_is_fail_fast(client):
    client.app.state.lock.acquire()
    try:
        response = client.post("/tools/mail/search", json={"query": {}})
        assert response.status_code == 503 and response.json()["error"] == "capacity_busy"
    finally:
        client.app.state.lock.release()
def test_cli_preserves_cyrillic_in_redirected_windows_output():
    import os
    from pathlib import Path
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "demo.py"), "--scenario", "proactive", "--approve-demo"],
        cwd=root, env={**os.environ, "PYTHONIOENCODING": "cp1252"},
        capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    output = result.stdout.decode("utf-8")
    assert any("\u0400" <= char <= "\u04ff" for char in output)
    assert "After repeated approvals: outbox = 1 CRM tasks = 1" in output
