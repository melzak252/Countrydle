from datetime import date, datetime
from typing import List, Optional, Union
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from schemas.user import UserDisplay


class WojewodztwoDisplay(BaseModel):
    id: int
    nazwa: str

    model_config = ConfigDict(from_attributes=True)


class WojewodztwodleStateSchema(BaseModel):
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


class WojewodztwoGuessBase(BaseModel):
    guess: str
    wojewodztwo_id: Optional[int] = None


class WojewodztwoGuessCreate(WojewodztwoGuessBase):
    user_id: int
    day_id: int
    answer: bool


class WojewodztwoGuessDisplay(BaseModel):
    id: int
    guess: str
    wojewodztwo_id: Optional[int]
    guessed_at: datetime
    answer: bool

    model_config = ConfigDict(from_attributes=True)


class WojewodztwoQuestionBase(BaseModel):
    question: str = Field(max_length=50)



class WojewodztwoQuestionCreate(BaseModel):
    user_id: int
    day_id: int
    original_question: str
    question: Optional[str]
    valid: bool
    answer: Optional[bool]
    explanation: str
    context: Optional[str]


class WojewodztwoQuestionDisplay(BaseModel):
    id: int
    original_question: str
    question: Optional[str]
    valid: bool
    answer: Optional[bool]
    explanation: str
    asked_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WojewodztwoQuestionEnhanced(BaseModel):
    original_question: str
    valid: bool
    question: Optional[str] = None
    explanation: Optional[str] = None


class WojewodztwodleStateResponse(BaseModel):
    user: UserDisplay
    date: str
    state: WojewodztwodleStateSchema
    guesses: List[WojewodztwoGuessDisplay]
    questions: List[WojewodztwoQuestionDisplay]
    wojewodztwo: Optional[WojewodztwoDisplay] = None


class WojewodztwodleEndStateResponse(WojewodztwodleStateResponse):
    wojewodztwo: WojewodztwoDisplay


class DayWojewodztwoDisplay(BaseModel):
    id: int
    wojewodztwo: WojewodztwoDisplay | None
    date: date

    model_config = ConfigDict(from_attributes=True)

