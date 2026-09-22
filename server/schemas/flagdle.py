from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from schemas.user import UserDisplay
from schemas.country import CountryDisplay


class FlagdleGuessBase(BaseModel):
    guess: str
    country_id: Optional[int] = None
    elapsed_seconds: Optional[int] = None


class FlagdleGuessCreate(BaseModel):
    guess: str
    country_id: Optional[int] = None
    day_id: int
    user_id: Optional[int] = None
    answer: bool = False
    distance_km: Optional[int] = None
    bearing_degrees: Optional[int] = None
    bearing_direction: Optional[str] = None
    bearing_arrow: Optional[str] = None
    matched_colors: Optional[List[str]] = None
    missed_colors: Optional[List[str]] = None
    remaining_colors_count: Optional[int] = None
    matched_symbols: Optional[List[str]] = None
    revealed_tile: Optional[int] = None
    elapsed_seconds: Optional[int] = None


class FlagdleGuessDisplay(BaseModel):
    id: int
    guess: str
    country_id: Optional[int] = None
    answer: bool
    distance_km: Optional[int] = None
    bearing_degrees: Optional[int] = None
    bearing_direction: Optional[str] = None
    bearing_arrow: Optional[str] = None
    matched_colors: List[str] = Field(default_factory=list)
    missed_colors: List[str] = Field(default_factory=list)
    remaining_colors_count: Optional[int] = None
    matched_symbols: List[str] = Field(default_factory=list)
    revealed_tile: Optional[int] = None
    guessed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FlagdleStateSchema(BaseModel):
    remaining_guesses: int = 6
    guesses_made: int = 0
    revealed_stage: int = 1
    is_game_over: bool = False
    won: bool = False
    points: int = 0

    model_config = ConfigDict(from_attributes=True)


class FlagdleStateResponse(BaseModel):
    user: Optional[UserDisplay] = None
    date: str
    state: FlagdleStateSchema
    guesses: List[FlagdleGuessDisplay] = Field(default_factory=list)
    flag_asset_url: Optional[str] = None
    country: Optional[CountryDisplay] = None

    model_config = ConfigDict(from_attributes=True)


class FlagdleCountryDisplay(BaseModel):
    id: int
    name: str
    official_name: Optional[str] = None
    iso2: str = ""

    model_config = ConfigDict(from_attributes=True)


class FlagdleSyncSchema(BaseModel):
    date: str
    state: FlagdleStateSchema
    guesses: List[FlagdleGuessBase] = Field(default_factory=list)


class DayFlagdleDisplay(BaseModel):
    id: int
    country: Optional[CountryDisplay] = None
    date: date

    model_config = ConfigDict(from_attributes=True)
