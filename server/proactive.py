"""NEW DEMO: event-driven, deterministic policy, no LLM or background scheduler.

A fixture delivery creates proposals autonomously. Each external-looking effect
still waits for a separate decision. Event keys deduplicate within this process.
"""
from pydantic import BaseModel, ConfigDict, Field

from server.actions import ActionRequest
from server.errors import DemoError
from server.mail_query.models import MailQuerySpecV2, MailSearchRequest


class DeliveryEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_key: str = Field(..., min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")


class ProactiveAgent:
    def __init__(self, query, mail, actions):
        self.query, self.mail, self.actions = query, mail, actions
        self.events: dict[str, dict] = {}

    def receive(self, owner, event_key):
        if event_key in self.events:
            event = self.events[event_key]
            proposals = [self.actions.view(owner, item["id"]) for item in event["proposals"]]
            finished = all(item["status"] in {"completed", "rejected"} for item in proposals)
            return {**event, "proposals": proposals, "duplicate": True,
                    "status": "reviewed" if finished else "awaiting_approval"}
        if len(self.events) >= 20 or len(self.actions.records) > 197:
            raise DemoError("demo_event_capacity", 503)
        # Search capacity is checked before the fixture delivery to avoid an orphan event.
        self.query.ensure_capacity()
        uid = self.mail.receive_fixture(event_key)
        result = self.query.search(owner, MailSearchRequest(
            query=MailQuerySpecV2(people=["alex@north.example.test"]), page_size=50))
        snapshot = self.query.owned(owner, result.result_set_id)
        ref = next(item.ref for row, item in zip(snapshot.rows, snapshot.items) if row.uid == uid)
        proposals = [self.actions.propose(owner, ActionRequest(kind=kind,
            result_set_id=result.result_set_id, ref=ref, text=text)) for kind, text in (
                ("reply", "Thank you. This is a synthetic acknowledgement pending approval."),
                ("bitrix_task", "Review the synthetic customer proposal"))]
        event = {"event_key": event_key, "status": "awaiting_approval", "simulated": True,
                 "policy": "fixed_demo_rule; no LLM", "duplicate": False,
                 "proposals": proposals, "result_set_id": result.result_set_id,
                 "trace": ["mail.received", "query.search", "crm.lookup", "actions.proposed", "human.review"]}
        self.events[event_key] = event
        return event
