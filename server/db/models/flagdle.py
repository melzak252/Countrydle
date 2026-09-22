from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db.base import Base


class FlagdleDay(Base):
    __tablename__ = "flagdle_days"

    id = Column(Integer, primary_key=True, index=True)
    country_id = Column(Integer, ForeignKey("countries.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, unique=True, index=True, nullable=False, default=func.current_date())
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

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
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
