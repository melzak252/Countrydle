from datetime import date, datetime
from typing import List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field
from db.models.continental import ContinentCode
from schemas.country import CountryDisplay
from schemas.countrydle import LeaderboardEntry
from schemas.user import UserDisplay


class ContinentalStateSchema(BaseModel):
    id: Optional[int] = None
    user_id: Optional[int] = None
    day_id: Optional[int] = None
    remaining_questions: int = 8
    remaining_guesses: int = 3
    questions_asked: int = 0
    guesses_made: int = 0
    is_game_over: bool = False
    won: bool = False
    points: int = 0

    model_config = ConfigDict(from_attributes=True)


class ContinentalGuessBase(BaseModel):
    guess: str
    country_id: Optional[int] = None
    elapsed_seconds: Optional[int] = None


class ContinentalGuessCreate(ContinentalGuessBase):
    user_id: Optional[int] = None
    day_id: int
    answer: bool


class ContinentalGuessDisplay(BaseModel):
    id: int
    guess: str
    country_id: Optional[int] = None
    answer: bool
    guessed_at: datetime
    elapsed_seconds: Optional[int] = None
    distance_km: Optional[int] = None
    bearing_degrees: Optional[int] = None
    bearing_direction: Optional[str] = None
    bearing_arrow: Optional[str] = None
    is_game_over: Optional[bool] = None
    won: Optional[bool] = None
    points: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class ContinentalQuestionBase(BaseModel):
    question: str = Field(max_length=200)


class ContinentalQuestionDisplay(BaseModel):
    id: int
    original_question: str
    question: Optional[str] = None
    valid: bool
    answer: Optional[bool] = None
    explanation: Optional[str] = None
    asked_at: datetime
    report_token: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class InvalidContinentalQuestionDisplay(BaseModel):
    id: int
    original_question: str
    valid: bool = False
    explanation: str

    model_config = ConfigDict(from_attributes=True)


class ContinentalStateResponse(BaseModel):
    user: Optional[UserDisplay] = None
    date: str
    state: ContinentalStateSchema
    questions: List[ContinentalQuestionDisplay]
    guesses: List[ContinentalGuessDisplay]
    country: Optional[CountryDisplay] = None


class ContinentalEndStateResponse(ContinentalStateResponse):
    country: CountryDisplay


class DayContinentalDisplay(BaseModel):
    id: int
    continent: ContinentCode
    country_id: int
    country: Optional[CountryDisplay] = None
    date: date

    model_config = ConfigDict(from_attributes=True)


class ContinentalGuessSyncItem(BaseModel):
    guess: str
    country_id: Optional[int] = None
    elapsed_seconds: Optional[int] = None


class ContinentalSyncSchema(BaseModel):
    date: str
    state: ContinentalStateSchema
    questions: List[int] = []
    guesses: List[ContinentalGuessSyncItem] = []
