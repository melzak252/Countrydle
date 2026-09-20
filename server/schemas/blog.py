from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict
from schemas.country import CountryDisplay


class BlogPostSummary(BaseModel):
    id: int
    date: date
    slug: str
    title: str
    subtitle: str
    reading_time_minutes: int
    summary: str
    country_name: str
    country_code: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BlogPostDisplay(BlogPostSummary):
    country_id: int
    fast_facts: Optional[Dict[str, Any]] = None
    fun_facts: List[Dict[str, Any]]
    deduction_masterclass: Optional[Dict[str, Any]] = None
    content_markdown: str
    country: Optional[CountryDisplay] = None
    player_stats: Optional[Dict[str, Any]] = None
    model_config = ConfigDict(from_attributes=True)


class BlogPostListResponse(BaseModel):
    total: int
    posts: List[BlogPostSummary]
