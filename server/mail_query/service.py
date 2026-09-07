"""SIMULATED Query Engine: exact casefolded metadata equality and newest first.

The closed engine's identity normalization, ranking and encrypted persistence
are absent. This small service exposes their architectural seams and exercises
the original contracts/projections with process-local snapshots.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from mail_connector.synthetic import SyntheticMailbox
from server.errors import DemoError
from .attention import MailAdvertisingAssessment, MailAttentionAssessment, MailAttentionEvidence
from .models import (MailMatchEvidence, MailReadIssue, MailReadRequest, MailReadResult,
                     MailSearchCounters, MailSearchItem, MailSearchRequest, MailSearchResult)
from .projection import project_read_item


@dataclass
class Snapshot:
    owner: str
    expires: datetime
    generation: int
    rows: list
    items: list[MailSearchItem]
    candidate_count: int
    processed_count: int
    partial: bool


class QueryService:
    def __init__(self, mailbox: SyntheticMailbox):
        self.mailbox = mailbox
        self.sets: dict[str, Snapshot] = {}
        self.groups = {"banks": ["bank@finance.example.test"]}
        self.scan_limit = 100
        self.byte_limit = 100_000  # Demo constants, not production configuration.
        self.total_byte_limit = 150_000
        self.total_char_limit = 2400

    def ensure_capacity(self):
        now = datetime.now(timezone.utc)
        self.sets = {key: value for key, value in self.sets.items() if value.expires > now}
        if len(self.sets) >= 100:
            raise DemoError("demo_capacity", 503)

    def owned(self, owner, set_id):
        snapshot = self.sets.get(set_id)
        if snapshot is None or snapshot.owner != owner:
            raise DemoError("result_set_not_found", 404)
        if snapshot.expires <= datetime.now(timezone.utc):
            raise DemoError("result_set_expired", 410)
        if snapshot.generation != self.mailbox.generation:
            raise DemoError("stale_uidvalidity", 409)
        return snapshot

    def search(self, owner: str, request: MailSearchRequest):
        if request.query is not None:
            query = request.query
            if any(group not in self.groups for group in query.groups):
                raise DemoError("group_not_found", 404)
            now = datetime.now(timezone.utc)
            self.ensure_capacity()
            candidates = [row for row in self.mailbox.metadata()
                          if (query.date_from is None or row.internal_date.date() >= query.date_from)
                          and (query.date_to is None or row.internal_date.date() <= query.date_to)]
            candidates.sort(key=lambda row: row.internal_date, reverse=True)
            rows, items = [], []
            for row in candidates[:self.scan_limit]:
                evidence = []
                contacts = [("from", row.sender)] + [("to", c) for c in row.to] + [("cc", c) for c in row.cc]
                selectors = [("person", p, [p]) for p in query.people]
                selectors += [("organization", p, [p]) for p in query.organizations]
                selectors += [("group", p, self.groups[p]) for p in query.groups]
                for kind, label, values in selectors:
                    for prefix, contact in contacts:
                        if contact is None:
                            continue
                        for field, value in (("name", contact.name), ("email", contact.email)):
                            if value and value.casefold() in [v.casefold() for v in values]:
                                evidence.append(MailMatchEvidence(entity_type=kind, query_value=label,
                                    field=f"{prefix}_{field}", match_kind="exact_email" if field == "email" else "exact_phrase"))
                if selectors and not evidence:
                    continue
                attention = None
                if row.sender and row.sender.email == "bank@finance.example.test":
                    attention = MailAttentionAssessment(advertising=MailAdvertisingAssessment(
                        label="possible_advertising", rule_points=1, rules_version="fixture-only",
                        evidence=[MailAttentionEvidence(code="synthetic_fixture_label", field="from_email",
                                  matched_value=row.sender.email, points=1)]))
                items.append(MailSearchItem(ref=uuid4().hex, received_at=row.internal_date,
                    subject=row.subject, sender_name=row.sender.name if row.sender else None,
                    sender_email=row.sender.email if row.sender else None,
                    unread=row.unread, size_bytes=row.size_bytes, match_evidence=evidence, attention=attention))
                rows.append(row)
            set_id = uuid4().hex
            snapshot = Snapshot(owner, now + timedelta(minutes=10), self.mailbox.generation,
                                rows, items, len(candidates), min(len(candidates), self.scan_limit),
                                len(candidates) > self.scan_limit)
            self.sets[set_id] = snapshot
        else:
            set_id = request.result_set_id
            snapshot = self.owned(owner, set_id)
        page = snapshot.items[request.cursor:request.cursor + request.page_size]
        end = request.cursor + len(page)
        return MailSearchResult(result_set_id=set_id, expires_at=snapshot.expires,
            coverage="partial_candidate_budget" if snapshot.partial else "complete",
            counters=MailSearchCounters(candidate_count=snapshot.candidate_count,
                processed_count=snapshot.processed_count,
                matched_count=len(snapshot.items), returned_count=len(page), failed_count=0),
            items=page, next_cursor=end if end < len(snapshot.items) else None)

    def resolve(self, owner, set_id, ref):
        snapshot = self.owned(owner, set_id)
        for row, item in zip(snapshot.rows, snapshot.items):
            if item.ref == ref:
                return row
        raise DemoError("message_ref_not_found", 404)

    def read(self, owner: str, request: MailReadRequest):
        snapshot = self.owned(owner, request.result_set_id)
        rows = [self.resolve(owner, request.result_set_id, ref) for ref in request.refs]
        items, issues = [], []
        total_bytes, chars = 0, self.total_char_limit
        coverage = "complete"
        for ref, row in zip(request.refs, rows):
            code = ("message_size_unknown" if row.size_bytes is None else
                    "message_too_large" if row.size_bytes > self.byte_limit else
                    "batch_byte_budget_exhausted" if total_bytes + row.size_bytes > self.total_byte_limit else None)
            if code:
                issues.append(MailReadIssue(ref=ref, code=code, size_bytes=row.size_bytes))
                coverage = "partial_size_budget"
                continue
            total_bytes += row.size_bytes
            try:
                fetched = self.mailbox.fetch(row.uid)
            except RuntimeError:
                issues.append(MailReadIssue(ref=ref, code="message_fetch_failed"))
                if coverage != "partial_size_budget":
                    coverage = "partial_provider_error"
                continue
            annotation = next(item.attention for item in snapshot.items if item.ref == ref)
            item = project_read_item(ref, fetched, row,
                body_char_limit=min(240 if request.detail == "preview" else 1800, chars),
                recipient_limit=5, attention=annotation)
            chars -= len(item.body)
            items.append(item)
            if item.body_truncated and coverage == "complete":
                coverage = "partial_context_budget"
        return MailReadResult(result_set_id=request.result_set_id, detail=request.detail,
                              coverage=coverage, items=items, issues=issues)
