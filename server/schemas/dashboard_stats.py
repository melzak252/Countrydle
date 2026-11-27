from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


LeaderboardPeriod = Literal["daily", "monthly", "all_time"]


class DistributionBucket(BaseModel):
    label: str
    count: int
    pct: float
    is_player: bool = False


class ModeDistributions(BaseModel):
    questions: Optional[List[DistributionBucket]] = None
    guesses: Optional[List[DistributionBucket]] = None
    score: Optional[List[DistributionBucket]] = None


class PlayerSummary(BaseModel):
    played: bool = False
    completed: bool = False
    won: bool = False
    is_guest: bool = False
    points: Optional[int] = None
    questions_used: Optional[int] = None
    guesses_used: Optional[int] = None
    score: Optional[int] = None
    max_score: Optional[int] = None
    elapsed_seconds: Optional[float] = None
    percentile: Optional[float] = None
    daily_rank: Optional[int] = None
    monthly_rank: Optional[int] = None
    all_time_rank: Optional[int] = None


class DashboardLeaderboardEntry(BaseModel):
    rank: int
    user_id: int
    username: str
    points: int
    wins: int
    games_played: int
    average_points: float
    best_score: Optional[int] = None
    best_elapsed_seconds: Optional[float] = None
    questions_used: Optional[int] = None
    guesses_used: Optional[int] = None
    is_current_user: bool = False


class DashboardLeaderboardResponse(BaseModel):
    mode: str
    period: LeaderboardPeriod
    date: str
    total_ranked: int
    entries: List[DashboardLeaderboardEntry] = Field(default_factory=list)
    current_user_entry: Optional[DashboardLeaderboardEntry] = None


class ModeStatsSummaryResponse(BaseModel):
    mode: str
    mode_kind: str
    is_daily: bool
    date: str
    played_today: int
    completed_today: int
    winners_today: int
    win_rate_pct: float
    avg_questions_won: Optional[float] = None
    avg_guesses_won: Optional[float] = None
    avg_score: Optional[float] = None
    avg_elapsed_seconds: Optional[float] = None
    distributions: ModeDistributions
    player: PlayerSummary
    leaderboard: DashboardLeaderboardResponse
