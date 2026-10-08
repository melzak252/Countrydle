from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from daily_clock import utc_today
from db.base import Base


class FlagdleDay(Base):
    __tablename__ = "flagdle_days"

    id = Column(Integer, primary_key=True, index=True)
    country_id = Column(Integer, ForeignKey("countries.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, unique=True, index=True, nullable=False, default=utc_today)
    created_at = Column(DateTime, default=func.now())

    country = relationship("Country")


class FlagdleState(Base):
    __tablename__ = "flagdle_states"
    __table_args__ = (
        UniqueConstraint("user_id", "day_id", name="uq_flagdle_user_day"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    day_id = Column(Integer, ForeignKey("flagdle_days.id", ondelete="CASCADE"), nullable=False, index=True)

    remaining_guesses = Column(Integer, nullable=False, default=12)
    questions_asked = Column(Integer, nullable=False, default=0, server_default="0")
    guesses_made = Column(Integer, nullable=False, default=0)
    revealed_stage = Column(Integer, nullable=False, default=1)
    is_game_over = Column(Boolean, nullable=False, default=False)
    won = Column(Boolean, nullable=False, default=False)
    points = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    day = relationship("FlagdleDay")
    user = relationship("User")


class FlagdleGuess(Base):
    __tablename__ = "flagdle_guesses"
    __table_args__ = (Index("ix_flagdle_guesses_guest_day", "guest_id", "day_id"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    guest_id = Column(String(36), nullable=True)
    day_id = Column(Integer, ForeignKey("flagdle_days.id", ondelete="CASCADE"), nullable=False, index=True)
    country_id = Column(Integer, ForeignKey("countries.id", ondelete="CASCADE"), nullable=True)
    guess = Column(String, nullable=False)

    answer = Column(Boolean, nullable=False, default=False)
    distance_km = Column(Integer, nullable=True)
    bearing_degrees = Column(Integer, nullable=True)
    bearing_direction = Column(String, nullable=True)
    bearing_arrow = Column(String, nullable=True)

    matched_colors = Column(JSON, nullable=True)
    missed_colors = Column(JSON, nullable=True)
    remaining_colors_count = Column(Integer, nullable=True)
    matched_symbols = Column(JSON, nullable=True)
    revealed_tile = Column(Integer, nullable=True)

    elapsed_seconds = Column(Integer, nullable=True)
    guessed_at = Column(DateTime, default=func.now())

    day = relationship("FlagdleDay")
    user = relationship("User")
    country = relationship("Country", foreign_keys=[country_id])


class FlagdleQuestion(Base):
    __tablename__ = "flagdle_questions"
    __table_args__ = (Index("ix_flagdle_questions_guest_day", "guest_id", "day_id"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    guest_id = Column(String(36), nullable=True)
    day_id = Column(Integer, ForeignKey("flagdle_days.id", ondelete="CASCADE"), nullable=False, index=True)
    original_question = Column(String, nullable=False)
    question = Column(String)
    valid = Column(Boolean, nullable=False)
    answer = Column(Boolean)
    explanation = Column(String, nullable=False)
    context = Column(String)
    fact_provenance = Column(JSON, nullable=False, default=list, server_default="[]")
    asked_at = Column(DateTime, server_default=func.now(), nullable=False)

    day = relationship("FlagdleDay")
    user = relationship("User")
