from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator


SuggestionTopic = Literal["feedback", "bug", "feature", "data"]


class SuggestionCreate(BaseModel):
    topic: SuggestionTopic = "feedback"
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
    name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None
    email: EmailStr | None = Field(default=None, max_length=254)

    model_config = ConfigDict(extra="forbid")

    @field_validator("name", "email", mode="before")
    @classmethod
    def normalize_optional_contact(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class SuggestionCreated(BaseModel):
    id: int


class SuggestionDisplay(BaseModel):
    id: int
    topic: SuggestionTopic
    message: str
    name: str | None
    email: EmailStr | None
    created_at: datetime
    reporter_username: str | None


class SuggestionList(BaseModel):
    items: list[SuggestionDisplay]
    total: int
