from datetime import datetime
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, computed_field, model_validator

from report_tokens import create_report_token
from schemas.fact_provenance import FactProvenanceRecord


AnswerReportMode = Literal["countrydle", "us_statedle", "powiatdle", "wojewodztwodle", "continental", "flagdle"]
AnswerReportStatus = Literal["open", "reviewed", "all"]


class ReportableQuestion(BaseModel):
    id: int
    report_mode: ClassVar[AnswerReportMode]

    @model_validator(mode="after")
    def protect_unverified_feedback(self):
        if getattr(self, "valid", None) is True and type(getattr(self, "answer", None)) is bool:
            return self
        # Provider diagnostics can disclose facts even after names are removed.
        # Warnings contain fixed guidance and only the player's original input.
        fields = type(self).model_fields
        if "explanation" in fields:
            self.explanation = "This question could not be verified. Please ask a clear yes/no question."
        if "question" in fields:
            self.question = self.original_question
        if "fact_provenance" in fields:
            self.fact_provenance = []
        return self

    @computed_field
    @property
    def report_token(self) -> str | None:
        return create_report_token(self.report_mode, self.id)


class AnswerReportCreate(BaseModel):
    mode: AnswerReportMode
    question_id: int = Field(gt=0, strict=True)
    comment: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    report_token: str | None = Field(default=None, max_length=256)

    model_config = ConfigDict(extra="forbid")


class AnswerReportCreated(BaseModel):
    id: int


class AnswerReportDetails(BaseModel):
    original_question: str
    question: str | None
    valid: bool
    answer: bool | None
    explanation: str
    context: str | None
    day_id: int
    game_date: str
    target_name: str
    server_version: str | None
    fact_provenance: list[FactProvenanceRecord] = Field(default_factory=list)


class AnswerReportDisplay(BaseModel):
    id: int
    mode: AnswerReportMode
    question_id: int
    comment: str
    created_at: datetime
    reviewed_at: datetime | None
    reporter_username: str | None
    details: AnswerReportDetails


class AnswerReportList(BaseModel):
    items: list[AnswerReportDisplay]
    total: int


class AnswerReportReview(BaseModel):
    reviewed: bool = Field(strict=True)

    model_config = ConfigDict(extra="forbid")
