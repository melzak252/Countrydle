from datetime import datetime
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, computed_field

from report_tokens import create_report_token


AnswerReportMode = Literal["countrydle", "us_statedle", "powiatdle", "wojewodztwodle"]
AnswerReportStatus = Literal["open", "reviewed", "all"]


class ReportableQuestion(BaseModel):
    id: int
    report_mode: ClassVar[AnswerReportMode]

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
