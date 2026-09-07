"""Typed, body-free metadata search contracts for Query Engine v1."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .folder import MailboxFolderState


class MailMetadataQuery(BaseModel):
    """Provider-independent predicates supported by the v1 connector."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    folder: Literal["INBOX"] = "INBOX"
    date_from: date | None = None
    date_to: date | None = None
    sender_email: str | None = Field(None, max_length=320)
    recipient_email: str | None = Field(None, max_length=320)
    only_unread: bool | None = None
    header_text: str | None = Field(None, max_length=500)
    body_text: str | None = Field(None, max_length=500)

    @field_validator("sender_email", "recipient_email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().casefold()
        if not normalized or "@" not in normalized or any(char.isspace() for char in normalized):
            raise ValueError("email predicate must be an exact email address")
        return normalized

    @field_validator("header_text", "body_text")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("text predicate must not be blank")
        return normalized

    @model_validator(mode="after")
    def validate_range(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must be <= date_to")
        return self


class MailContactMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str | None = None
    email: str


class MailDeliveryHints(BaseModel):
    """Small metadata-only delivery signals used by server annotations.

    Raw list URLs and header values are intentionally not retained.  The
    Query Engine only needs bounded presence/normalised hints and must not
    turn transport headers into a body search surface.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    list_id_present: bool = False
    list_unsubscribe_present: bool = False
    precedence: str | None = Field(None, max_length=64)
    auto_submitted: str | None = Field(None, max_length=64)


class MailMessageMetadata(BaseModel):
    """Immutable search snapshot. Internal UID fields never cross Server API."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    folder: Literal["INBOX"] = "INBOX"
    uidvalidity: int = Field(..., gt=0)
    uid: int = Field(..., gt=0)
    internal_date: datetime
    mime_date: datetime | None = None
    subject: str | None = None
    sender: MailContactMetadata | None = None
    to: list[MailContactMetadata] = Field(default_factory=list)
    cc: list[MailContactMetadata] = Field(default_factory=list)
    unread: bool
    size_bytes: int | None = Field(None, ge=0)
    message_id: str | None = None
    delivery_hints: MailDeliveryHints = Field(default_factory=MailDeliveryHints)


class MailMetadataIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    uid: int | None = Field(None, gt=0)
    stage: Literal["search", "metadata"]
    code: str


class MailMetadataSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["mail_metadata_search_v1"] = "mail_metadata_search_v1"
    query: MailMetadataQuery
    folder_state: MailboxFolderState
    candidate_count: int = Field(..., ge=0)
    processed_count: int = Field(..., ge=0)
    matched_count: int = Field(..., ge=0)
    returned_count: int = Field(..., ge=0)
    failed_count: int = Field(..., ge=0)
    candidate_budget_exhausted: bool = False
    provider_error: bool = False
    timed_out: bool = False
    messages: list[MailMessageMetadata] = Field(default_factory=list)
    issues: list[MailMetadataIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_counts(self):
        attempted = self.processed_count + self.failed_count
        if attempted > self.candidate_count:
            raise ValueError("metadata counters are inconsistent")
        if self.matched_count != len(self.messages):
            raise ValueError("matched_count must equal metadata snapshot size")
        if self.returned_count != self.matched_count:
            raise ValueError("connector returns the full matched snapshot")
        return self


class MailConnectorCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["mail_connector_capabilities_v1"] = (
        "mail_connector_capabilities_v1"
    )
    batch_metadata: bool = True
    provider_body_search: Literal["supported", "unsupported", "unknown"] = "unknown"
