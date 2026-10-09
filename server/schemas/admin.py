from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from schemas.fact_provenance import FactProvenanceRecord


class AdminModeToday(BaseModel):
    mode_key: str
    mode_label: str
    target_name: str
    players: int
    winners: int
    win_rate_pct: float
    questions: int
    guesses: int
    avg_questions_won: Optional[float] = 0.0
    avg_guesses_won: Optional[float] = 0.0
    model_config = ConfigDict(from_attributes=True)


class AdminDaySummary(BaseModel):
    date: date
    total_players: int
    total_winners: int
    win_rate_pct: float
    total_questions: int
    total_guesses: int
    avg_questions_won: Optional[float] = 0.0
    avg_guesses_won: Optional[float] = 0.0
    model_config = ConfigDict(from_attributes=True)


class AdminOverviewToday(BaseModel):
    total_players: int
    total_winners: int
    win_rate_pct: float
    total_questions: int
    total_guesses: int
    avg_questions_won: Optional[float] = 0.0
    avg_guesses_won: Optional[float] = 0.0
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
    target_name: Optional[str] = None
    target_subtitle: Optional[str] = None
    source: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AdminLiveGuess(BaseModel):
    id: int
    mode: str
    username: str
    guess: str
    answer: bool
    guessed_at: Optional[datetime] = None
    target_name: Optional[str] = None
    target_subtitle: Optional[str] = None

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


class QuestionTokenUsage(BaseModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    thought_tokens: int | None = Field(default=None, ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class QuestionModelDiagnostics(BaseModel):
    # Explicit allowlist: prompts, messages, credentials and raw responses stay private.
    provider: str | None = None
    model: str | None = None
    model_version: str | None = None
    contract_version: str | None = None
    duration_ms: float | None = Field(default=None, ge=0)
    cache_hit: bool | None = None
    usage: QuestionTokenUsage | None = None


class QuestionDiagnostics(BaseModel):
    planner: QuestionModelDiagnostics | None = None
    local_duration_ms: float | None = Field(default=None, ge=0)
    retrieval_duration_ms: float | None = Field(default=None, ge=0)
    fallback: QuestionModelDiagnostics | None = None


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
    diagnostics: QuestionDiagnostics
    fact_provenance: list[FactProvenanceRecord] = Field(default_factory=list)


AdminQuestionSource = Literal["local_kb", "fallback", "invalid"]


class AdminQuestionItem(BaseModel):
    id: int
    mode: str
    day_id: int
    game_date: str
    target_id: int
    target_name: str
    target_subtitle: Optional[str] = None
    user_id: Optional[int] = None
    username: str
    is_guest: bool
    original_question: str
    question: Optional[str] = None
    valid: bool
    answer: Optional[bool] = None
    explanation: str
    context: Optional[str] = None
    source: AdminQuestionSource
    relation: Optional[str] = None
    asked_at: Optional[datetime] = None
    has_report: bool = False
    report_id: Optional[int] = None
    fact_provenance: list[FactProvenanceRecord] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class AdminQuestionsListResponse(BaseModel):
    items: List[AdminQuestionItem]
    total: int
    page: int
    limit: int


class AdminGameSessionTimelineEvent(BaseModel):
    event_type: Literal["question", "guess"]
    id: int
    timestamp: Optional[datetime] = None
    question: Optional[str] = None
    original_question: Optional[str] = None
    valid: Optional[bool] = None
    answer: Optional[bool] = None
    explanation: Optional[str] = None
    source: Optional[AdminQuestionSource] = None
    relation: Optional[str] = None
    context: Optional[str] = None
    guess: Optional[str] = None
    correct: Optional[bool] = None


class AdminGameSessionItem(BaseModel):
    session_id: str
    mode: str
    day_id: int
    game_date: str
    target_name: str
    target_subtitle: Optional[str] = None
    user_id: Optional[int] = None
    username: str
    is_guest: bool
    status: Literal["won", "lost", "in_progress"]
    questions_asked: int
    guesses_made: int
    duration_seconds: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    timeline: List[AdminGameSessionTimelineEvent] = Field(default_factory=list)


class AdminGameSessionsResponse(BaseModel):
    items: List[AdminGameSessionItem]
    total: int
    page: int
    limit: int


class AdminTopQuestionStat(BaseModel):
    text: str
    count: int
    yes_pct: float
    win_correlation: float


class AdminTopGuessStat(BaseModel):
    guess: str
    count: int
    correct_pct: float


class AdminTargetStrategyStats(BaseModel):
    target_name: str
    target_subtitle: Optional[str] = None
    game_date: str
    total_players: int
    win_rate_pct: float
    top_questions: List[AdminTopQuestionStat] = Field(default_factory=list)
    top_guesses: List[AdminTopGuessStat] = Field(default_factory=list)
    avg_questions_winners: float = 0.0
    avg_questions_losers: float = 0.0


class AdminInvalidateFallbackRequest(BaseModel):
    mode: str
    question_id: int


class AdminInvalidateFallbackResponse(BaseModel):
    success: bool
    mode: str
    question_id: int
    message: str
