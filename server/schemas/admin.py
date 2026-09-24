from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class AdminModeToday(BaseModel):
    mode_key: str
    mode_label: str
    target_name: str
    players: int
    winners: int
    win_rate_pct: float
    questions: int
    guesses: int

    model_config = ConfigDict(from_attributes=True)


class AdminDaySummary(BaseModel):
    date: date
    total_players: int
    total_winners: int
    win_rate_pct: float
    total_questions: int
    total_guesses: int

    model_config = ConfigDict(from_attributes=True)


class AdminOverviewToday(BaseModel):
    total_players: int
    total_winners: int
    win_rate_pct: float
    total_questions: int
    total_guesses: int

    model_config = ConfigDict(from_attributes=True)


class AdminPlatformTotals(BaseModel):
    total_users: int
    total_games: int
    total_questions: int
    total_guesses: int
    total_blog_posts: int

    model_config = ConfigDict(from_attributes=True)


class AdminOverviewResponse(BaseModel):
    today: AdminOverviewToday
    modes_today: List[AdminModeToday]
    history_14d: List[AdminDaySummary]
    totals: AdminPlatformTotals


class AdminUserItem(BaseModel):
    id: int
    username: str
    email: str
    created_at: Optional[datetime] = None
    is_admin: bool
    total_points: int
    total_wins: int
    games_played: int
    current_streak: int

    model_config = ConfigDict(from_attributes=True)


class AdminUsersResponse(BaseModel):
    total: int
    users: List[AdminUserItem]


class AdminLiveQuestion(BaseModel):
    id: int
    mode: str
    username: str
    question: str
    valid: bool
    answer: Optional[bool] = None
    explanation: Optional[str] = None
    asked_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AdminLiveGuess(BaseModel):
    id: int
    mode: str
    username: str
    guess: str
    answer: bool
    guessed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AdminLiveFeedResponse(BaseModel):
    recent_questions: List[AdminLiveQuestion]
    recent_guesses: List[AdminLiveGuess]


AdminQuestionTestMode = Literal[
    "countrydle", "us_statedle", "powiatdle", "wojewodztwodle",
    "europe", "asia", "africa", "americas", "flagdle",
]


class AdminQuestionTestEntity(BaseModel):
    id: int
    name: str


class AdminQuestionTestRequest(BaseModel):
    mode: AdminQuestionTestMode
    entity_id: int = Field(gt=0, strict=True)
    question: str = Field(min_length=1, max_length=100)

    model_config = ConfigDict(extra="forbid")

    @field_validator("question", mode="before")
    @classmethod
    def trim_question(cls, value):
        return value.strip() if isinstance(value, str) else value


class AdminQuestionTestResponse(BaseModel):
    mode: AdminQuestionTestMode
    entity: AdminQuestionTestEntity
    original_question: str
    question: str | None
    valid: bool
    answer: bool | None
    explanation: str
    context: str | None
    source: Literal["local_kb", "local_planner", "fallback", "flag_kb"]
    server_version: str
    duration_ms: int
    plan: Dict[str, Any] | None
