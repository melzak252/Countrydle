from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.answer_report import ReportableQuestion
from schemas.countrydle import CountrydleStateSchema
from schemas.user import UserDisplay


class EnglishCountyDisplay(BaseModel):
    id: int
    name: str
    region: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CountydleStateSchema(BaseModel):
    id: int
    user_id: int
    day_id: int
    remaining_questions: int
    remaining_guesses: int
    questions_asked: int
    guesses_made: int
    is_game_over: bool
    won: bool
    points: int

    model_config = ConfigDict(from_attributes=True)


class EnglishCountyGuessBase(BaseModel):
    guess: str
    county_id: Optional[int] = None
    elapsed_seconds: Optional[int] = None


class EnglishCountyGuessCreate(EnglishCountyGuessBase):
    user_id: Optional[int] = None
    day_id: int
    answer: bool


class EnglishCountyGuessDisplay(BaseModel):
    id: int
    guess: str
    county_id: Optional[int]
    guessed_at: datetime
    answer: bool
    distance_km: Optional[int] = None
    bearing_degrees: Optional[int] = None
    bearing_direction: Optional[str] = None
    bearing_arrow: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class EnglishCountyQuestionBase(BaseModel):
    question: str = Field(max_length=100)


class EnglishCountyQuestionCreate(BaseModel):
    user_id: Optional[int]
    day_id: int
    original_question: str
    question: Optional[str]
    valid: bool
    answer: Optional[bool] = Field(strict=True)
    explanation: str
    context: Optional[str]
    intent: Optional[str] = None
    required_info: Optional[str] = None


class EnglishCountyQuestionDisplay(ReportableQuestion):
    report_mode = "countydle"

    id: int
    original_question: str
    question: Optional[str]
    valid: bool
    answer: Optional[bool]
    explanation: str
    asked_at: datetime
    user_id: Optional[int] = None
    day_id: int
    context: Optional[str] = Field(default=None, exclude=True)
    user: Optional[UserDisplay] = None
    county: Optional[EnglishCountyDisplay] = None

    model_config = ConfigDict(from_attributes=True)


class EnglishCountyQuestionEnhanced(BaseModel):
    original_question: str
    valid: bool
    question: Optional[str] = None
    explanation: Optional[str] = None
    intent: Optional[str] = None
    required_info: Optional[str] = None


class CountydleStateResponse(BaseModel):
    user: UserDisplay | None = None
    date: str
    state: CountydleStateSchema
    guesses: List[EnglishCountyGuessDisplay]
    questions: List[EnglishCountyQuestionDisplay]
    county: Optional[EnglishCountyDisplay] = None


class CountydleEndStateResponse(CountydleStateResponse):
    county: EnglishCountyDisplay = Field(...)


class DayEnglishCountyDisplay(BaseModel):
    id: int
    county: EnglishCountyDisplay | None
    date: date

    model_config = ConfigDict(from_attributes=True)


class CountydleSyncSchema(BaseModel):
    state: CountrydleStateSchema
    questions: List[int]
    guesses: List[EnglishCountyGuessBase]
    date: str
