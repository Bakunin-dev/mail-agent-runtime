"""Read-only mailbox generation identity used to validate ResultSets."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MailboxFolderState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    folder: str = Field(..., min_length=1)
    uidvalidity: int = Field(..., gt=0)
    uidnext: int | None = Field(None, gt=0)
    highest_modseq: int | None = Field(None, ge=0)
