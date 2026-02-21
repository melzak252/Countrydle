from datetime import date, datetime
from typing import List, Optional, Union
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from schemas.user import UserDisplay


class USStateDisplay(BaseModel):
    id: int
    name: str
    code: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class USStatedleStateSchema(BaseModel):
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


class USStateGuessBase(BaseModel):
    guess: str
    us_state_id: Optional[int] = None


class USStateGuessCreate(USStateGuessBase):
    user_id: int
    day_id: int
    answer: bool


class USStateGuessDisplay(BaseModel):
    id: int
    guess: str
    us_state_id: Optional[int]
    guessed_at: datetime
    answer: bool

    model_config = ConfigDict(from_attributes=True)


class USStateQuestionBase(BaseModel):
    question: str = Field(max_length=50)



class USStateQuestionCreate(BaseModel):
    user_id: int
    day_id: int
    original_question: str
    question: Optional[str]
    valid: bool
    answer: Optional[bool]
    explanation: str
    context: Optional[str]


class USStateQuestionDisplay(BaseModel):
    id: int
    original_question: str
    question: Optional[str]
    valid: bool
    answer: Optional[bool]
    explanation: str
    asked_at: datetime

    model_config = ConfigDict(from_attributes=True)


class USStateQuestionEnhanced(BaseModel):
    original_question: str
    valid: bool
    question: Optional[str] = None
    explanation: Optional[str] = None


class USStatedleStateResponse(BaseModel):
    user: UserDisplay
    date: str
    state: USStatedleStateSchema
    guesses: List[USStateGuessDisplay]
    questions: List[USStateQuestionDisplay]
    us_state: Optional[USStateDisplay] = None


class USStatedleEndStateResponse(USStatedleStateResponse):
    us_state: USStateDisplay = Field(...)


class DayUSStateDisplay(BaseModel):
    id: int
    us_state: USStateDisplay | None
    date: date

    model_config = ConfigDict(from_attributes=True)

