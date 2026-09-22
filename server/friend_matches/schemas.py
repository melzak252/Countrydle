from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

Mode = Literal[
    "countrydle", "us_statedle", "wojewodztwodle", "powiatdle",
    "europe", "asia", "africa", "americas"
]
HumanAnswer = Literal["yes", "mostly_yes", "mostly_no", "no", "unknown"]
ActionType = Literal["select_secret", "randomize_secret", "ready", "ask", "answer", "guess", "pass", "correct_answer", "offer_draw", "accept_draw", "decline_draw", "leave", "rematch"]
Comparison = Literal["all", "agree", "disagree", "not_comparable", "ai_invalid", "ai_unavailable", "pending_ai"]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CreateRequest(InputModel):
    name: str = Field(min_length=1, max_length=40)
    mode: Mode
    request_id: UUID


class JoinRequest(InputModel):
    name: str = Field(min_length=1, max_length=40)
    request_id: UUID


class EntityPayload(InputModel):
    entity_id: str = Field(min_length=1, max_length=128)


class ReadyPayload(InputModel):
    ready: StrictBool


class AskPayload(InputModel):
    question: str = Field(min_length=3, max_length=500)


class AnswerPayload(InputModel):
    question_id: UUID
    answer: HumanAnswer
    observed_ai_question_id: UUID | None = None


class CorrectionPayload(InputModel):
    question_id: UUID
    answer: HumanAnswer
    expected_revision: int = Field(ge=1)
    observed_ai_question_id: UUID | None = None


class ActionRequest(InputModel):
    action_id: UUID
    expected_version: int = Field(ge=1)
    type: ActionType
    payload: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_payload(self):
        schema = {
            "select_secret": EntityPayload, "guess": EntityPayload,
            "ready": ReadyPayload, "ask": AskPayload, "answer": AnswerPayload,
            "correct_answer": CorrectionPayload,
        }.get(self.type, InputModel)
        self.payload = schema.model_validate(self.payload).model_dump(mode="json")
        return self


class ReportRequest(InputModel):
    comment: str = Field(min_length=3, max_length=2000)


class ReviewRequest(InputModel):
    status: Literal["new", "confirmed", "needs_evidence", "subjective", "rejected", "fixed"]
    note: str = Field(default="", max_length=5000)
