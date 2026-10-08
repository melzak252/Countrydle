"""Evidence for the selected local country fact families."""
from datetime import date, datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FactProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["unknown", "cited"] = "unknown"
    citation: str | None = None
    source_url: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    retrieved_at: datetime | None = None
    updated_at: datetime | None = None
    convention: str | None = None

    @field_validator("source_url")
    @classmethod
    def safe_source_url(cls, value):
        if value is not None:
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None or parsed.password is not None:
                raise ValueError("Source URL must be absolute HTTP(S) without credentials")
        return value

    @model_validator(mode="after")
    def validate_interval(self):
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not precede effective_from")
        if self.status == "cited" and (not self.citation or not self.source_url):
            raise ValueError("Cited evidence requires a citation and source URL")
        return self


class FactProvenanceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    relation: Literal["membership", "hemisphere"]
    value: str | None
    provenance: FactProvenance


class PublicFactEvidence(BaseModel):
    """Default-deny target-linked explanations/evidence; terminal serializers opt in."""
    fact_provenance: list[FactProvenanceRecord] = Field(default_factory=list)

    @field_validator("fact_provenance", mode="before")
    @classmethod
    def redact_active_evidence(cls, value, info):
        if not (info.context or {}).get("terminal"):
            return []
        return value or []

    @field_validator("explanation", check_fields=False)
    @classmethod
    def protect_factual_explanation(cls, value, info):
        answered = info.data.get("valid") is True and type(info.data.get("answer")) is bool
        if answered and not (info.context or {}).get("terminal"):
            return ""
        return value

    @field_validator("question", check_fields=False)
    @classmethod
    def protect_provider_rewrite(cls, value, info):
        if not (info.context or {}).get("terminal"):
            return info.data.get("original_question", value)
        return value
