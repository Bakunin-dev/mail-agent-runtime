"""Bounded read projection regression tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from mail_connector.models.metadata import MailContactMetadata, MailMessageMetadata  # noqa: E402
from server.mail_query.models import (  # noqa: E402
    MailReadIssue,
    MailReadItem,
    MailReadResult,
    MailSearchCounters,
    MailSearchItem,
    MailSearchResult,
)
from server.mail_query.projection import project_read_item  # noqa: E402
from server.mail_query.portal_projection import format_read_text, format_search_text  # noqa: E402


def _metadata() -> MailMessageMetadata:
    return MailMessageMetadata(
        uidvalidity=1,
        uid=1,
        internal_date=datetime(2026, 8, 17, tzinfo=timezone.utc),
        subject="Уведомление",
        sender=MailContactMetadata(name="Sender", email="sender@example.test"),
        unread=True,
    )


def test_empty_body_with_attachment_is_explicitly_attachment_only() -> None:
    package = SimpleNamespace(
        body="",
        subject="Уведомление",
        sender=SimpleNamespace(name="Sender", email="sender@example.test"),
        recipients=SimpleNamespace(to=[], cc=[]),
        attachments=[SimpleNamespace(name="Реквизиты.doc")],
    )
    message = SimpleNamespace(
        result=SimpleNamespace(email=package),
        warnings=[],
        unread=True,
    )
    item = project_read_item(
        "opaque-ref",
        message,
        _metadata(),
        body_char_limit=800,
        recipient_limit=5,
    )
    assert item.content_state == "attachment_only"
    assert item.body == ""
    assert "attachment_only_content" in item.warning_codes
    assert item.attachment_names == ["Реквизиты.doc"]


def test_portal_search_projection_explains_pagination_and_partial_coverage() -> None:
    result = MailSearchResult(
        result_set_id="result-set-123456",
        coverage="partial_candidate_budget",
        counters=MailSearchCounters(
            candidate_count=5000,
            processed_count=5000,
            matched_count=2,
            returned_count=1,
            failed_count=0,
        ),
        items=[
            MailSearchItem(
                ref="opaque-ref-1",
                received_at=datetime(2026, 8, 21, tzinfo=timezone.utc),
                subject="Subject",
                sender_name="Sender",
                sender_email="sender@example.test",
                unread=True,
            )
        ],
        next_cursor=1,
        expires_at=datetime(2026, 8, 22, tzinfo=timezone.utc),
    )

    text = format_search_text(result)

    assert "status: more results available; continue with cursor 1" in text
    assert "status: coverage is partial; do not treat this ResultSet as exhaustive" in text


def test_portal_read_projection_explains_byte_and_attachment_limits() -> None:
    result = MailReadResult(
        result_set_id="result-set-123456",
        detail="preview",
        coverage="partial_size_budget",
        items=[
            MailReadItem(
                ref="opaque-ref-1",
                received_at=datetime(2026, 8, 21, tzinfo=timezone.utc),
                subject="Attachment",
                sender_name="Sender",
                sender_email="sender@example.test",
                unread=True,
                body="",
                content_state="attachment_only",
                attachment_names=["document.pdf"],
                warning_codes=["attachment_only_content"],
            )
        ],
        issues=[
            MailReadIssue(
                ref="opaque-ref-2",
                code="message_too_large",
                size_bytes=20_000_000,
            )
        ],
    )

    text = format_read_text(
        result,
        handle_by_ref={"opaque-ref-1": "m1", "opaque-ref-2": "m2"},
    )

    assert "some selected message content was not loaded because of the configured byte limit" in text
    assert "status: m1 | body is empty; attachment metadata is available" in text
    assert "status: m2 | message content was not loaded because of the configured byte limit" in text


def main() -> None:
    test_empty_body_with_attachment_is_explicitly_attachment_only()
    test_portal_search_projection_explains_pagination_and_partial_coverage()
    test_portal_read_projection_explains_byte_and_attachment_limits()
    print("PASS: test_empty_body_with_attachment_is_explicitly_attachment_only")
    print("PASS: test_portal_search_projection_explains_pagination_and_partial_coverage")
    print("PASS: test_portal_read_projection_explains_byte_and_attachment_limits")
    print("ALL PROJECTION TESTS PASSED")


if __name__ == "__main__":
    main()
