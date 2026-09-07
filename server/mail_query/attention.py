"""Original assessment DTOs; production rule engine is intentionally omitted."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AdvertisingLabel = Literal["likely_advertising", "possible_advertising", "not_detected"]


class MailAttentionEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    code: str = Field(..., min_length=1, max_length=64)
    field: Literal["from_email", "subject", "list_id", "list_unsubscribe", "precedence"]
    matched_value: str = Field(..., min_length=1, max_length=200)
    points: int = Field(..., ge=0, le=100)


class MailAdvertisingAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    label: AdvertisingLabel
    rule_points: int = Field(..., ge=0, le=100)
    rules_version: str = Field(..., min_length=1, max_length=100)
    evidence: list[MailAttentionEvidence] = Field(default_factory=list)


class MailAttentionAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    contract_version: Literal["mail_attention_assessment_v1"] = "mail_attention_assessment_v1"
    advertising: MailAdvertisingAssessment
