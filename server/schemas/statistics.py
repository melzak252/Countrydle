from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel, ConfigDict
from schemas.user import ProfileDisplay


class GameHistoryEntry(BaseModel):
    date: str
    won: bool
    points: int
    attempts: int
    target_name: str

    model_config = ConfigDict(from_attributes=True)


class GameStatistics(BaseModel):
    points: int
    wins: int
    games_played: int
    completed_games: int
    win_rate: float
    streak: int
    best_streak: int
    average_points: float
    average_winning_guesses: float
    history: List[GameHistoryEntry]

    model_config = ConfigDict(from_attributes=True)


class FriendMatchHistoryEntry(BaseModel):
    id: str
    finished_at: datetime
    mode: str
    outcome: Literal["won", "lost", "draw"]

    model_config = ConfigDict(from_attributes=True)


class FriendMatchStatistics(BaseModel):
    games_played: int
    wins: int
    losses: int
    draws: int
    win_rate: float
    history: List[FriendMatchHistoryEntry]

    model_config = ConfigDict(from_attributes=True)


class UserProfileStatistics(BaseModel):
    user: ProfileDisplay
    countrydle: GameStatistics
    powiatdle: GameStatistics
    us_statedle: GameStatistics
    wojewodztwodle: GameStatistics
    flagdle: GameStatistics
    europe: GameStatistics
    asia: GameStatistics
    africa: GameStatistics
    americas: GameStatistics
    friend_matches: FriendMatchStatistics

    model_config = ConfigDict(from_attributes=True)
