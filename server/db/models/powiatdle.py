from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from daily_clock import utc_today
from db.base import Base


class PowiatdleDay(Base):
    __tablename__ = "powiatdle_days"

    id = Column(Integer, primary_key=True, index=True)
    powiat_id = Column(Integer, ForeignKey("powiaty.id"))
    date = Column(Date, nullable=False, default=utc_today)

    powiat = relationship("Powiat")


class PowiatdleState(Base):
    __tablename__ = "powiatdle_states"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    day_id = Column(Integer, ForeignKey("powiatdle_days.id"))
    remaining_questions = Column(Integer, nullable=False, default=15)
    remaining_guesses = Column(Integer, nullable=False, default=3)
    questions_asked = Column(Integer, nullable=False, default=0)
    guesses_made = Column(Integer, nullable=False, default=0)
    is_game_over = Column(Boolean, nullable=False, default=False)
    won = Column(Boolean, nullable=False, default=False)
    points = Column(Integer, nullable=False, default=0)

    user = relationship("User")
    day = relationship("PowiatdleDay")


class PowiatdleGuess(Base):
    __tablename__ = "powiatdle_guesses"
    __table_args__ = (Index("ix_powiatdle_guesses_guest_day", "guest_id", "day_id"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    guest_id = Column(String(36), nullable=True)
    day_id = Column(Integer, ForeignKey("powiatdle_days.id"))
    elapsed_seconds = Column(Integer, nullable=True)
    guess = Column(String, nullable=False)
    powiat_id = Column(Integer, ForeignKey("powiaty.id"), nullable=True)
    guessed_at = Column(DateTime, default=func.now())
    answer = Column(Boolean)

    user = relationship("User")
    day = relationship("PowiatdleDay")
    powiat = relationship("Powiat")


class PowiatdleQuestion(Base):
    __tablename__ = "powiatdle_questions"
    __table_args__ = (Index("ix_powiatdle_questions_guest_day", "guest_id", "day_id"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    guest_id = Column(String(36), nullable=True)
    day_id = Column(Integer, ForeignKey("powiatdle_days.id"))
    context = Column(String)
    original_question = Column(String, nullable=False)
    question = Column(String)
    valid = Column(Boolean, nullable=False)
    answer = Column(Boolean)
    explanation = Column(String, nullable=False)
    asked_at = Column(DateTime, default=func.now())

    user = relationship("User")
    day = relationship("PowiatdleDay")
