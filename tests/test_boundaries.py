"""Publication, isolation, and resource-boundary regressions."""
import asyncio
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from server.actions import ActionRequest
from server.app import Session
from server.errors import DemoError
from server.mail_query.models import MailQuerySpecV2, MailReadRequest, MailSearchRequest


def test_event_does_not_arrive_when_query_capacity_is_full():
    session = Session()
    for _ in range(100):
        session.query.search("alice", MailSearchRequest(query=MailQuerySpecV2()))
    count = len(session.mail.messages)
    with pytest.raises(DemoError, match="demo_capacity"):
        session.agent.receive("alice", "full")
    assert len(session.mail.messages) == count and not session.actions.records


def test_event_at_last_available_slot_and_repeat_has_current_status():
    session = Session()
    for _ in range(99):
        session.query.search("alice", MailSearchRequest(query=MailQuerySpecV2()))
    event = session.agent.receive("alice", "last-slot")
    for proposal in event["proposals"]:
        session.actions.decide("alice", proposal["id"], True)
    repeated = session.agent.receive("alice", "last-slot")
    assert repeated["status"] == "reviewed"
    assert all(item["status"] == "completed" for item in repeated["proposals"])


def test_snapshot_counters_do_not_change_when_demo_limit_changes():
    session = Session()
    result = session.query.search("alice", MailSearchRequest(query=MailQuerySpecV2(), page_size=1))
    session.query.scan_limit = 2
    page = session.query.search("alice", MailSearchRequest(result_set_id=result.result_set_id, cursor=1))
    assert page.counters.processed_count == result.counters.processed_count == 12


def test_total_byte_and_character_budgets():
    session = Session()
    result = session.query.search("alice", MailSearchRequest(query=MailQuerySpecV2()))
    session.query.total_byte_limit = 1
    read = session.query.read("alice", MailReadRequest(result_set_id=result.result_set_id,
                               refs=[result.items[0].ref]))
    assert read.issues[0].code == "batch_byte_budget_exhausted"
    assert session.mail.fetch_count == 0
    session.query.total_byte_limit = 150_000
    session.query.total_char_limit = 10
    read = session.query.read("alice", MailReadRequest(result_set_id=result.result_set_id,
                               refs=[result.items[0].ref, result.items[1].ref]))
    assert sum(len(item.body) for item in read.items) == 10
    assert read.coverage == "partial_context_budget"


def test_action_copy_cannot_be_used_to_change_approved_payload():
    session = Session()
    request = ActionRequest(kind="send", recipient="first@example.test", text="Initial text")
    proposal = session.actions.propose("alice", request)
    proposal["payload"]["recipient"] = "other@example.test"
    request.text = "Changed text"
    session.actions.decide("alice", proposal["id"], True)
    assert session.mail.outbox[0]["recipient"] == "first@example.test"
    assert session.mail.outbox[0]["text"] == "Initial text"


def test_portal_bridge_uses_loopback_and_has_no_approval_tool():
    from openwebui_tools.mail_agent_demo import Tools
    original_client = httpx.AsyncClient
    seen = []
    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, text="MAIL SEARCH synthetic")
    def client_factory(**kwargs):
        assert kwargs["base_url"] == "http://127.0.0.1:8765" and kwargs["trust_env"] is False
        return original_client(**kwargs, transport=httpx.MockTransport(handler))
    async def broken_emitter(_event):
        raise RuntimeError("UI unavailable")
    with patch("openwebui_tools.mail_agent_demo.httpx.AsyncClient", side_effect=client_factory):
        result = asyncio.run(Tools().mail_search('{"query":{}}', broken_emitter))
    assert "MAIL SEARCH" in result and len(seen) == 1
    assert not any("approv" in name or "decision" in name for name in dir(Tools))


def test_no_network_is_needed_for_full_in_process_scenario():
    import socket
    session = Session()
    with patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden")):
        event = session.agent.receive("alice", "offline")
        for proposal in event["proposals"]:
            session.actions.decide("alice", proposal["id"], True)
    assert len(session.crm.tasks) == len(session.mail.outbox) == 1


def test_modules_resolve_inside_public_root():
    import server.mail_query.models as models
    import mail_connector.synthetic as mail
    import bitrix_connector.synthetic as crm
    root = Path(__file__).resolve().parents[1]
    for module in (models, mail, crm):
        assert Path(module.__file__).resolve().is_relative_to(root)
