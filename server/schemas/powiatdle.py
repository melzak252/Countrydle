from datetime import date, datetime
from typing import List, Optional, Union
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from schemas.user import UserDisplay


class PowiatDisplay(BaseModel):
    id: int
    nazwa: str

    model_config = ConfigDict(from_attributes=True)


class PowiatdleStateSchema(BaseModel):
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


class PowiatGuessBase(BaseModel):
    guess: str
    powiat_id: Optional[int] = None


class PowiatGuessCreate(PowiatGuessBase):
    user_id: int
    day_id: int
    answer: bool


class PowiatGuessDisplay(BaseModel):
    id: int
    guess: str
    powiat_id: Optional[int]
    guessed_at: datetime
    answer: bool

    model_config = ConfigDict(from_attributes=True)


class PowiatQuestionBase(BaseModel):
    question: str = Field(max_length=50)



class PowiatQuestionCreate(BaseModel):
    user_id: int
    day_id: int
    original_question: str
    question: Optional[str]
    valid: bool
    answer: Optional[bool]
    explanation: str
    context: Optional[str]


class PowiatQuestionDisplay(BaseModel):
    id: int
    original_question: str
    question: Optional[str]
    valid: bool
    answer: Optional[bool]
    explanation: str
    asked_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PowiatQuestionEnhanced(BaseModel):
    original_question: str
    valid: bool
    question: Optional[str] = None
    explanation: Optional[str] = None


class PowiatdleStateResponse(BaseModel):
    user: UserDisplay
    date: str
    state: PowiatdleStateSchema
    guesses: List[PowiatGuessDisplay]
    questions: List[PowiatQuestionDisplay]
    powiat: Optional[PowiatDisplay] = None


class PowiatdleEndStateResponse(PowiatdleStateResponse):
    powiat: PowiatDisplay


class DayPowiatDisplay(BaseModel):
    id: int
    powiat: PowiatDisplay | None
    date: date

    model_config = ConfigDict(from_attributes=True)

