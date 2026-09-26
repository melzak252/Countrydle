from datetime import datetime, timezone
from typing import List

from pydantic import BaseModel, field_validator


class PatchNoteItem(BaseModel):
    id: int
    version: str
    title: str
    body: str
    published_at: datetime

    @field_validator("published_at")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class PatchNoteListResponse(BaseModel):
    items: List[PatchNoteItem]
    total: int
    page: int
    limit: int
