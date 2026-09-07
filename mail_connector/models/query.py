"""Explicit full-message fetch contracts used by mail_read."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mail_connector.models.result import ConnectorResult


class MailFetchIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    uid: str | None = None
    stage: Literal["fetch", "parse"]
    message: str


class FetchedMail(BaseModel):
    """A full message plus its stable mailbox identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["fetched_mail_v1"] = "fetched_mail_v1"
    message_ref: str = Field(..., min_length=1)
    mailbox_id: str = Field(..., min_length=1)
    folder: str
    uid: str
    uidvalidity: int | None = None
    mailbox_address: str | None = None
    mailbox_aliases: list[str] = Field(default_factory=list)
    corporate_domains: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    unread: bool
    result: ConnectorResult
    warnings: list[str] = Field(default_factory=list)


class MailFetchBatch(BaseModel):
    """Result of an explicit bounded UID fetch; it is not a search result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["mail_fetch_batch_v2"] = "mail_fetch_batch_v2"
    mailbox_id: str
    folder: str
    uidvalidity: int
    requested_count: int = Field(..., ge=0)
    returned_count: int = Field(..., ge=0)
    messages: list[FetchedMail] = Field(default_factory=list)
    issues: list[MailFetchIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_counts(self):
        if self.returned_count != len(self.messages):
            raise ValueError("returned_count must equal len(messages)")
        if self.returned_count > self.requested_count:
            raise ValueError("returned_count cannot exceed requested_count")
        return self
