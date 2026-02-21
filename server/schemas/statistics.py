from pydantic import BaseModel, ConfigDict
from typing import List
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
    streak: int = 0
    history: List[GameHistoryEntry]

    model_config = ConfigDict(from_attributes=True)

class UserProfileStatistics(BaseModel):
    user: ProfileDisplay
    countrydle: GameStatistics
    powiatdle: GameStatistics
    us_statedle: GameStatistics
    wojewodztwodle: GameStatistics

    model_config = ConfigDict(from_attributes=True)
