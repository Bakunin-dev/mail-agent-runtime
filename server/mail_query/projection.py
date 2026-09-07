"""Public body projection for bounded mail_read responses."""

from __future__ import annotations

from mail_connector.models.query import FetchedMail

from mail_connector.models.metadata import MailMessageMetadata

from .attention import MailAttentionAssessment
from .models import MailReadItem


def project_read_item(
    ref: str,
    message: FetchedMail,
    metadata: MailMessageMetadata,
    *,
    body_char_limit: int,
    recipient_limit: int,
    attention: MailAttentionAssessment | None = None,
) -> MailReadItem:
    package = message.result.email
    recipients = [
        item.email
        for item in (*package.recipients.to, *package.recipients.cc)
        if item.email
    ]
    original_body = package.body
    body = original_body[:body_char_limit]
    body_truncated = len(body) < len(original_body)
    warning_codes = list(dict.fromkeys(message.warnings))
    content_state = (
        "body_available"
        if original_body
        else "attachment_only"
        if package.attachments
        else "empty"
    )
    if content_state == "attachment_only":
        warning_codes.append("attachment_only_content")
    if body_truncated:
        warning_codes.append("body_truncated_context_budget")
    return MailReadItem(
        ref=ref,
        received_at=metadata.internal_date,
        subject=package.subject,
        sender_name=package.sender.name,
        sender_email=package.sender.email,
        recipient_emails=recipients[:recipient_limit],
        recipient_count=len(recipients),
        recipients_truncated=len(recipients) > recipient_limit,
        unread=message.unread,
        body=body,
        content_state=content_state,
        original_body_chars=len(original_body),
        body_truncated=body_truncated,
        attachment_names=[item.name for item in package.attachments],
        warning_codes=warning_codes,
        attention=attention,
    )
