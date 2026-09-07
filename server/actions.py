"""NEW DEMO: proposal -> explicit decision -> simulated effect.

No model can grant its own approval. The CLI/Swagger user calls decide explicitly.
Demo session names are not authentication; this is a loopback teaching server.
"""
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from bitrix_connector.synthetic import SyntheticBitrix
from mail_connector.synthetic import SyntheticMailbox
from server.errors import DemoError
from server.mail_query.service import QueryService

ActionKind = Literal["draft", "send", "reply", "forward", "mark_read", "move", "bitrix_task"]


class ActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: ActionKind
    result_set_id: str | None = None
    ref: str | None = None
    recipient: str | None = Field(None, max_length=200)
    text: str = Field("", max_length=2000)
    folder: Literal["Archive", "Processed"] = "Processed"

    @field_validator("recipient")
    @classmethod
    def fixture_address(cls, value):
        if value is not None:
            parts = value.casefold().split("@")
            if len(parts) != 2 or not parts[0] or not parts[1].endswith(".test") or any(c.isspace() for c in value):
                raise ValueError("only synthetic .test recipients are accepted")
        return value

    @model_validator(mode="after")
    def required_fields(self):
        if self.kind in {"reply", "forward", "mark_read", "move", "bitrix_task"} and not (self.result_set_id and self.ref):
            raise ValueError("this action requires an owned ResultSet and ref")
        if self.kind in {"send", "forward", "draft"} and not self.recipient:
            raise ValueError("recipient required")
        if self.kind in {"send", "forward", "reply", "draft", "bitrix_task"} and not self.text.strip():
            raise ValueError("non-empty text required")
        return self


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approve: bool


class Actions:
    def __init__(self, query: QueryService, mail: SyntheticMailbox, crm: SyntheticBitrix):
        self.query, self.mail, self.crm = query, mail, crm
        self.records: dict[str, dict] = {}

    def propose(self, owner, request: ActionRequest):
        if len(self.records) >= 200:
            raise DemoError("demo_action_capacity", 503)
        payload = {"text": request.text}
        if request.recipient:
            payload["recipient"] = request.recipient
        if request.ref:
            row = self.query.resolve(owner, request.result_set_id, request.ref)
            payload["uid"] = row.uid
            payload["subject"] = row.subject
            if request.kind == "reply":
                if row.sender is None:
                    raise DemoError("sender_missing")
                payload["recipient"] = row.sender.email
            if request.kind == "move":
                payload["folder"] = request.folder
            if request.kind == "bitrix_task":
                contact = self.crm.find_contact(row.sender.email if row.sender else "")
                if contact is None:
                    raise DemoError("crm_contact_not_found", 404)
                payload["contact_id"] = contact["id"]
        action_id = uuid4().hex
        self.records[action_id] = {
            "id": action_id, "owner": owner, "kind": request.kind, "payload": payload,
            "status": "pending", "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
            "request": request.model_copy(deep=True), "attempts": 0, "simulated": True,
        }
        return self.view(owner, action_id)

    def _owned(self, owner, action_id):
        record = self.records.get(action_id)
        if record is None or record["owner"] != owner:
            raise DemoError("action_not_found", 404)
        return record

    def view(self, owner, action_id):
        record = self._owned(owner, action_id)
        return {key: {k: v for k, v in value.items() if k != "uid"} if isinstance(value, dict) else value
                for key, value in record.items() if key not in {"owner", "request"}}

    def decide(self, owner, action_id, approve):
        record = self._owned(owner, action_id)
        if record["status"] in {"completed", "rejected"}:
            return self.view(owner, action_id)
        if record["expires_at"] <= datetime.now(timezone.utc):
            record["status"] = "expired"
            raise DemoError("approval_expired", 410)
        if not approve:
            record["status"] = "rejected"
            return self.view(owner, action_id)
        request = record["request"]
        if request.ref:
            self.query.resolve(owner, request.result_set_id, request.ref)
        record["attempts"] += 1
        try:
            payload = record["payload"]
            if record["kind"] == "bitrix_task":
                result = self.crm.create_task(payload["text"], payload["contact_id"])
            else:
                result = self.mail.apply(record["kind"], payload.copy())
        except RuntimeError:
            record["status"] = "failed"
            record["error"] = "simulated_connector_failure"
            return self.view(owner, action_id)
        record.update(status="completed", result=result)
        record.pop("error", None)
        return self.view(owner, action_id)
