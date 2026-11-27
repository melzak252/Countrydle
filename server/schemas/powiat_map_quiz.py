from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class DailyMapQuizAnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    guess_id: StrictInt = Field(gt=0)
    expected_round: StrictInt = Field(ge=0, lt=10)


class MapQuizAnswerProgress(BaseModel):
    round: int
    target_name: str
    guess_id: int
    correct: bool


class MapQuizAnswerResult(BaseModel):
    round: int
    guess_id: int
    correct: bool


class DailyMapQuizState(BaseModel):
    date: date
    round_count: int
    expected_round: int
    current_target: str | None
    score: int
    is_complete: bool
    answers: list[MapQuizAnswerProgress]
    last_answer: MapQuizAnswerResult | None = None


class MapQuizHistoryEntry(BaseModel):
    date: date
    score: int
    round_count: int
    completed_at: datetime
    answers: list[MapQuizAnswerProgress]


class MapQuizHistoryResponse(BaseModel):
    items: list[MapQuizHistoryEntry]
    total: int


class MapQuizDailyStats(BaseModel):
    date: date
    completed_count: int | None
    average_score: float | None
    score_distribution: dict[str, int] | None
