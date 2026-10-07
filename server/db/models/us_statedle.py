from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from daily_clock import utc_today
from db.base import Base


class USStatedleDay(Base):
    __tablename__ = "us_statedle_days"

    id = Column(Integer, primary_key=True, index=True)
    us_state_id = Column(Integer, ForeignKey("us_states.id"))
    date = Column(Date, nullable=False, default=utc_today)

    us_state = relationship("USState")


class USStatedleState(Base):
    __tablename__ = "us_statedle_states"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    day_id = Column(Integer, ForeignKey("us_statedle_days.id"))
    remaining_questions = Column(Integer, nullable=False, default=8)
    remaining_guesses = Column(Integer, nullable=False, default=3)
    questions_asked = Column(Integer, nullable=False, default=0)
    guesses_made = Column(Integer, nullable=False, default=0)
    is_game_over = Column(Boolean, nullable=False, default=False)
    won = Column(Boolean, nullable=False, default=False)
    points = Column(Integer, nullable=False, default=0)

    user = relationship("User")
    day = relationship("USStatedleDay")


class USStatedleGuess(Base):
    __tablename__ = "us_statedle_guesses"
    __table_args__ = (Index("ix_us_statedle_guesses_guest_day", "guest_id", "day_id"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    guest_id = Column(String(36), nullable=True)
    day_id = Column(Integer, ForeignKey("us_statedle_days.id"))
    elapsed_seconds = Column(Integer, nullable=True)
    guess = Column(String, nullable=False)
    us_state_id = Column(Integer, ForeignKey("us_states.id"), nullable=True)
    guessed_at = Column(DateTime, default=func.now())
    answer = Column(Boolean)

    user = relationship("User")
    day = relationship("USStatedleDay")
    us_state = relationship("USState")


class USStatedleQuestion(Base):
    __tablename__ = "us_statedle_questions"
    __table_args__ = (Index("ix_us_statedle_questions_guest_day", "guest_id", "day_id"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    guest_id = Column(String(36), nullable=True)
    day_id = Column(Integer, ForeignKey("us_statedle_days.id"))
    context = Column(String)
    original_question = Column(String, nullable=False)
    question = Column(String)
    valid = Column(Boolean, nullable=False)
    answer = Column(Boolean)
    explanation = Column(String, nullable=False)
    asked_at = Column(DateTime, default=func.now())

    user = relationship("User")
    day = relationship("USStatedleDay")
