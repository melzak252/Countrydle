from datetime import date, datetime, timezone
import json
import re
from sys import float_info
from typing import Annotated, Any, Dict, List, Literal, Optional, Union
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, StrictBool, StrictFloat, StrictInt, StrictStr, TypeAdapter, field_validator, model_validator
from schemas.country import CountryDisplay

class BlogSourceLink(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=1, max_length=2048)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        parsed = TypeAdapter(HttpUrl).validate_python(value)
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("Source URLs must not include credentials")
        normalized = str(parsed)
        if len(normalized) > 2048:
            raise ValueError("Normalized source URLs must not exceed 2048 characters")
        return normalized


BlogFactValue = Union[
    StrictStr, Annotated[StrictInt, Field(ge=-int(float_info.max), le=int(float_info.max))],
    Annotated[StrictFloat, Field(allow_inf_nan=False)], StrictBool, None,
]


class BlogCuriosity(BaseModel):
    title: StrictStr
    description: StrictStr

    model_config = ConfigDict(extra="allow")


class BlogDeductionStep(BaseModel):
    question: StrictStr
    answer: Optional[StrictStr] = None
    explanation: Optional[StrictStr] = None

    model_config = ConfigDict(extra="allow")

    @field_validator("answer", "explanation")
    @classmethod
    def optional_strings_cannot_be_null(cls, value):
        if value is None:
            raise ValueError("Omit unknown step fields instead of setting them to null")
        return value


# Match client cleanDisplayText exactly: unescape only these punctuation marks,
# then trim ECMAScript whitespace. Citation warnings and reference numbers stay.
_DISPLAY_ESCAPES = re.compile(r"\\([_()[\]*])")
_DISPLAY_WHITESPACE = "\u0009\u000a\u000b\u000c\u000d\u0020\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"


def _clean_quiz_display_text(value: str) -> str:
    return _DISPLAY_ESCAPES.sub(r"\1", value).strip(_DISPLAY_WHITESPACE)


class BlogTriviaQuiz(BaseModel):
    question: StrictStr
    correct_answer: StrictStr
    incorrect_distractor: StrictStr
    explanation: StrictStr

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    @field_validator("question", "correct_answer", "incorrect_distractor", "explanation")
    @classmethod
    def require_meaningful_quiz_text(cls, value: str) -> str:
        if not value:
            raise ValueError("Quiz fields must contain nonblank text")
        return value

    @model_validator(mode="after")
    def require_distinct_answers(self):
        if (
            _clean_quiz_display_text(self.correct_answer).casefold()
            == _clean_quiz_display_text(self.incorrect_distractor).casefold()
        ):
            raise ValueError("Quiz answer and distractor must display distinct choices")
        return self


class BlogDeductionMasterclass(BaseModel):
    steps: Optional[List[BlogDeductionStep]] = None
    pro_tip: Optional[StrictStr] = None
    quiz: Optional[BlogTriviaQuiz] = None

    model_config = ConfigDict(extra="allow")

    @field_validator("steps", "pro_tip", "quiz")
    @classmethod
    def optional_fields_cannot_be_null(cls, value):
        if value is None:
            raise ValueError("Omit unknown deduction fields instead of setting them to null")
        return value


class BlogReviewInput(BaseModel):
    expected_updated_at: AwareDatetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("expected_updated_at", mode="before")
    @classmethod
    def require_raw_timestamp_string(cls, value):
        if not isinstance(value, str):
            raise ValueError("Send the exact updated_at string loaded for this article")
        return value

    @field_validator("expected_updated_at")
    @classmethod
    def normalize_review_version(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)


class BlogPostUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=240)
    subtitle: Optional[str] = Field(default=None, min_length=1, max_length=500)
    summary: Optional[str] = Field(default=None, min_length=1, max_length=10000)
    fast_facts: Optional[Dict[str, BlogFactValue]] = None
    fun_facts: Optional[List[BlogCuriosity]] = Field(default=None, max_length=50)
    deduction_masterclass: Optional[BlogDeductionMasterclass] = None
    content_markdown: Optional[str] = Field(default=None, min_length=1, max_length=100000)
    source_links: Optional[List[BlogSourceLink]] = Field(default=None, max_length=20)
    editorial_note: Optional[str] = Field(default=None, max_length=10000)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("fast_facts", "fun_facts", "deduction_masterclass")
    @classmethod
    def limit_json_size(cls, value):
        serializable = TypeAdapter(Any).dump_python(value, mode="json", exclude_unset=True)
        if value is not None and len(json.dumps(serializable, ensure_ascii=False)) > 100000:
            raise ValueError("Editorial JSON fields must not exceed 100000 characters")
        return value

    @model_validator(mode="after")
    def validate_patch(self):
        editable_fields = self.model_fields_set & BlogPostUpdate.model_fields.keys()
        if not editable_fields:
            raise ValueError("Supply at least one editable field")
        nullable = {"fast_facts", "deduction_masterclass", "editorial_note"}
        for field in editable_fields - nullable:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class BlogPostEditInput(BlogPostUpdate, BlogReviewInput):
    """Editable content plus the exact article version inspected by the editor."""



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
    continent: Optional[str] = None
    difficulty: Optional[str] = None
    win_rate_pct: Optional[float] = None
    total_players: Optional[int] = None
    created_at: Optional[datetime]
    updated_at: datetime
    editorial_status: Literal["unreviewed", "reviewed"] = "unreviewed"

    model_config = ConfigDict(from_attributes=True)

    @field_validator("created_at", "updated_at")
    @classmethod
    def utc_timestamps(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is None:
            return None
        # Legacy database columns store naive UTC timestamps.
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

class TopQuestionStat(BaseModel):
    question: str
    answer: str
    count: int
    pct: Optional[int] = None
    explanation: Optional[str] = None


class WrongGuessStat(BaseModel):
    guess: str
    count: int


class CommunityGameDebrief(BaseModel):
    has_telemetry: bool = False
    total_challengers: int = 0
    total_solvers: int = 0
    win_rate_pct: float = 0.0
    avg_questions_to_win: float = 0.0
    avg_guesses: float = 0.0
    high_score: Optional[int] = None
    top_questions: List[TopQuestionStat] = []
    common_pitfalls: List[WrongGuessStat] = []
    decisive_clue: Optional[str] = None


class BlogPostDisplay(BlogPostSummary):
    country_id: int
    fast_facts: Optional[Dict[str, Any]] = None
    fun_facts: List[Dict[str, Any]]
    deduction_masterclass: Optional[Dict[str, Any]] = None
    content_markdown: str
    country: Optional[CountryDisplay] = None
    player_stats: Optional[Dict[str, Any]] = None
    game_debrief: Optional[CommunityGameDebrief] = None
    related_posts: Optional[List[BlogPostSummary]] = None
    source_links: List[BlogSourceLink] = Field(default_factory=list)
    editorial_note: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    reviewer_name: Optional[str] = None
    ai_assisted: bool = True
    model_config = ConfigDict(from_attributes=True)

    @field_validator("reviewed_at")
    @classmethod
    def utc_review_timestamp(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is None:
            return None
        return cls.utc_timestamps(value)


class BlogPostListResponse(BaseModel):
    total: int
    posts: List[BlogPostSummary]
