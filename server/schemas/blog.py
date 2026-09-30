from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict
from schemas.country import CountryDisplay


class BlogPostSummary(BaseModel):
    id: int
    date: date
    slug: str
    title: str
    subtitle: str
    reading_time_minutes: int
    summary: str
    country_name: str
    country_code: Optional[str] = None
    continent: Optional[str] = None
    difficulty: Optional[str] = None
    win_rate_pct: Optional[float] = None
    total_players: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TopQuestionStat(BaseModel):
    question: str
    answer: str
    count: int
    pct: Optional[int] = None
    explanation: Optional[str] = None


class WrongGuessStat(BaseModel):
    guess: str
    count: int


class CommunityGameDebrief(BaseModel):
    has_telemetry: bool = False
    total_challengers: int = 0
    total_solvers: int = 0
    win_rate_pct: float = 0.0
    avg_questions_to_win: float = 0.0
    avg_guesses: float = 0.0
    high_score: Optional[int] = None
    top_questions: List[TopQuestionStat] = []
    common_pitfalls: List[WrongGuessStat] = []
    decisive_clue: Optional[str] = None


class BlogPostDisplay(BlogPostSummary):
    country_id: int
    fast_facts: Optional[Dict[str, Any]] = None
    fun_facts: List[Dict[str, Any]]
    deduction_masterclass: Optional[Dict[str, Any]] = None
    content_markdown: str
    country: Optional[CountryDisplay] = None
    player_stats: Optional[Dict[str, Any]] = None
    game_debrief: Optional[CommunityGameDebrief] = None
    related_posts: Optional[List[BlogPostSummary]] = None
    model_config = ConfigDict(from_attributes=True)


class BlogPostListResponse(BaseModel):
    total: int
    posts: List[BlogPostSummary]
