"""Public Query Engine contracts; IMAP identities remain deliberately absent."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .attention import MailAttentionAssessment


CoverageCode = Literal[
    "complete",
    "partial_candidate_budget",
    "partial_timeout",
    "partial_provider_error",
    "partial_metadata_error",
    "partial_context_budget",
    "partial_size_budget",
    "unsupported_predicate",
    "stale_uidvalidity",
    "result_set_expired",
]


class MailQuerySpecV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["mail_query_spec_v2"] = "mail_query_spec_v2"
    folder: Literal["INBOX"] = "INBOX"
    date_from: date | None = Field(
        default=None,
        description="Hard inclusive lower date bound for the metadata search.",
    )
    date_to: date | None = Field(
        default=None,
        description="Hard inclusive upper date bound for the metadata search.",
    )
    people: list[str] = Field(
        default_factory=list,
        max_length=20,
        description=(
            "People identities searched deterministically across From, To, and Cc "
            "metadata. Do not put topics or semantic phrases here."
        ),
    )
    organizations: list[str] = Field(
        default_factory=list,
        max_length=20,
        description=(
            "Organization identities searched deterministically across mail metadata. "
            "Do not put topics, products, or semantic phrases here."
        ),
    )
    groups: list[str] = Field(
        default_factory=list,
        max_length=10,
        description=(
            "Configured broad sender-identity groups. Use a configured group name, "
            "not a topic or semantic phrase."
        ),
    )

    @field_validator("people", "organizations", "groups")
    @classmethod
    def normalize_identity_values(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            clean = value.strip()
            if not clean:
                raise ValueError("identity values must not be blank")
            if len(clean) > 200:
                raise ValueError("identity values must not exceed 200 characters")
            normalized.append(clean)
        return list(dict.fromkeys(normalized))

    @model_validator(mode="after")
    def validate_range(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must be <= date_to")
        return self


class MailSearchRequest(BaseModel):
    """Start a broad immutable ResultSet search or page an existing ResultSet."""

    model_config = ConfigDict(extra="forbid")

    query: MailQuerySpecV2 | None = Field(
        default=None,
        description=(
            "Start a new immutable ResultSet with a broad date and identity "
            "metadata search."
        ),
    )
    result_set_id: str | None = Field(
        default=None,
        min_length=16,
        max_length=100,
        description=(
            "Existing ResultSet to page. Use with cursor; do not repeat the original "
            "search merely to see the next page."
        ),
    )
    cursor: int = Field(
        0,
        ge=0,
        description=(
            "Continue the existing immutable ResultSet from the next cursor returned "
            "by search. Use 0 for a new search."
        ),
    )
    page_size: int = Field(
        20,
        ge=1,
        le=50,
        description=(
            "Number of metadata candidates in this page (1-50). This is not a "
            "semantic relevance limit."
        ),
    )

    @model_validator(mode="after")
    def validate_mode(self):
        if (self.query is None) == (self.result_set_id is None):
            raise ValueError("provide exactly one of query or result_set_id")
        if self.query is not None and self.cursor:
            raise ValueError("a new search must start at cursor 0")
        return self


class MailSearchCounters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_count: int = Field(..., ge=0)
    processed_count: int = Field(..., ge=0)
    matched_count: int = Field(..., ge=0)
    returned_count: int = Field(..., ge=0)
    failed_count: int = Field(..., ge=0)


class MailMatchEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_type: Literal["person", "organization", "group"]
    query_value: str
    field: Literal[
        "from_name",
        "from_email",
        "to_name",
        "to_email",
        "cc_name",
        "cc_email",
    ]
    match_kind: Literal[
        "exact_email",
        "exact_domain",
        "transliterated_domain",
        "exact_phrase",
        "exact_tokens",
        "repaired_whitespace",
    ]


class MailSearchItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ref: str
    received_at: datetime
    mime_date: datetime | None = None
    subject: str | None = None
    sender_name: str | None = None
    sender_email: str | None = None
    recipient_emails: list[str] = Field(default_factory=list)
    recipient_count: int = Field(0, ge=0)
    recipients_truncated: bool = False
    unread: bool
    size_bytes: int | None = Field(None, ge=0)
    match_evidence: list[MailMatchEvidence] = Field(default_factory=list)
    attention: MailAttentionAssessment | None = None


class MailSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal[
        "mail_search_result_v1", "mail_search_result_v2", "mail_search_result_v3"
    ] = (
        "mail_search_result_v3"
    )
    operation: Literal["mail_search"] = "mail_search"
    result_set_id: str
    coverage: CoverageCode
    counters: MailSearchCounters
    items: list[MailSearchItem] = Field(default_factory=list)
    next_cursor: int | None = Field(None, ge=0)
    expires_at: datetime


class MailReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_set_id: str = Field(
        ...,
        min_length=16,
        max_length=100,
        description="Owned ResultSet created by mail_search; only its selected refs may be read.",
    )
    refs: list[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description=(
            "Selected opaque message refs from this ResultSet. Read only messages "
            "needed for the user's answer."
        ),
    )
    detail: Literal["preview", "full"] = Field(
        "full",
        description=(
            "preview gives small bounded content for deciding whether a message "
            "deserves deeper reading; full gives larger bounded prepared content "
            "for a message already selected as useful. Preview is optional."
        ),
    )

    @field_validator("refs")
    @classmethod
    def unique_refs(cls, refs: list[str]) -> list[str]:
        if len(refs) != len(set(refs)):
            raise ValueError("refs must be unique")
        return refs


class MailReadItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ref: str
    received_at: datetime
    subject: str | None = None
    sender_name: str | None = None
    sender_email: str | None = None
    recipient_emails: list[str] = Field(default_factory=list)
    recipient_count: int = Field(0, ge=0)
    recipients_truncated: bool = False
    unread: bool
    body: str
    content_state: Literal["body_available", "attachment_only", "empty"] = "empty"
    original_body_chars: int = Field(0, ge=0)
    body_truncated: bool = False
    attachment_names: list[str] = Field(default_factory=list)
    warning_codes: list[str] = Field(default_factory=list)
    attention: MailAttentionAssessment | None = None


class MailReadIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ref: str
    code: str
    size_bytes: int | None = Field(None, ge=0)


class MailReadResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["mail_read_result_v2", "mail_read_result_v3"] = (
        "mail_read_result_v3"
    )
    operation: Literal["mail_read"] = "mail_read"
    result_set_id: str
    detail: Literal["preview", "full"]
    coverage: CoverageCode
    items: list[MailReadItem] = Field(default_factory=list)
    issues: list[MailReadIssue] = Field(default_factory=list)

