from typing import List, Optional

from pydantic import BaseModel, Field


class MapQuizEntity(BaseModel):
    id: int
    name: str
    aliases: List[str] = Field(default_factory=list)
    latitude: float
    longitude: float


class MapQuizTarget(BaseModel):
    id: int
    name: str


class MapQuizRoundAnswer(BaseModel):
    round: int
    target_id: int
    target_name: str
    clicked_id: int
    clicked_name: str
    correct: bool


class MapQuizDailyState(BaseModel):
    session_id: str
    scope: str
    date: str
    total_rounds: int
    current_round: int
    current_target: Optional[MapQuizTarget] = None
    answers: List[MapQuizRoundAnswer] = Field(default_factory=list)
    score: int
    is_completed: bool
    points: Optional[int] = None
    elapsed_seconds: Optional[int] = None
    ranked: bool = True


class MapQuizAnswerRequest(BaseModel):
    entity_id: int
    round: Optional[int] = None


class MapQuizAnswerResponse(BaseModel):
    result: MapQuizRoundAnswer
    state: MapQuizDailyState
