from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict


TemplateDivergenceStatus = Literal["open", "reviewed", "all"]


class TemplateDivergenceDisplay(BaseModel):
    id: int
    mode: str
    question: str
    template_plan: Any
    gemini_plan: Any | None
    divergence_type: str
    details: dict[str, Any] | None
    created_at: datetime
    reviewed_at: datetime | None


class TemplateDivergenceList(BaseModel):
    items: list[TemplateDivergenceDisplay]
    total: int


class TemplateDivergenceReview(BaseModel):
    reviewed: bool

    model_config = ConfigDict(extra="forbid")
