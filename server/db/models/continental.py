from datetime import date
from enum import StrEnum
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship
from db.base import Base


class ContinentCode(StrEnum):
    EUROPE = "europe"
    ASIA = "asia"
    AFRICA = "africa"
    AMERICAS = "americas"


class ContinentalDay(Base):
    __tablename__ = "continental_days"

    id = Column(Integer, primary_key=True, index=True)
    continent = Column(
        Enum(
            ContinentCode,
            name="continent_code_enum",
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=False,
        ),
        nullable=False,
        index=True,
    )
    country_id = Column(Integer, ForeignKey("countries.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False, default=func.now(), index=True)

    country = relationship("Country")

    __table_args__ = (
        UniqueConstraint("continent", "date", name="uq_continental_days_continent_date"),
    )


class ContinentalState(Base):
    __tablename__ = "continental_states"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    day_id = Column(Integer, ForeignKey("continental_days.id", ondelete="CASCADE"), nullable=False, index=True)
    remaining_questions = Column(Integer, nullable=False, default=8)
    remaining_guesses = Column(Integer, nullable=False, default=3)
    questions_asked = Column(Integer, nullable=False, default=0)
    guesses_made = Column(Integer, nullable=False, default=0)
    is_game_over = Column(Boolean, nullable=False, default=False)
    won = Column(Boolean, nullable=False, default=False)
    points = Column(Integer, nullable=False, default=0)

    user = relationship("User")
    day = relationship("ContinentalDay")

    __table_args__ = (
        UniqueConstraint("user_id", "day_id", name="uq_continental_states_user_day"),
    )


class ContinentalGuess(Base):
    __tablename__ = "continental_guesses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    day_id = Column(Integer, ForeignKey("continental_days.id", ondelete="CASCADE"), nullable=False, index=True)
    guess = Column(String, nullable=False)
    country_id = Column(Integer, ForeignKey("countries.id", ondelete="SET NULL"), nullable=True)
    guessed_at = Column(DateTime, server_default=func.now(), nullable=False)
    answer = Column(Boolean, nullable=False)
    elapsed_seconds = Column(Integer, nullable=True)

    user = relationship("User")
    day = relationship("ContinentalDay")
    country = relationship("Country")


class ContinentalQuestion(Base):
    __tablename__ = "continental_questions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    day_id = Column(Integer, ForeignKey("continental_days.id", ondelete="CASCADE"), nullable=False, index=True)
    original_question = Column(String, nullable=False)
    question = Column(String, nullable=True)
    valid = Column(Boolean, nullable=False)
    answer = Column(Boolean, nullable=True)
    explanation = Column(String, nullable=True)
    context = Column(String, nullable=True)
    asked_at = Column(DateTime, server_default=func.now(), nullable=False)

    user = relationship("User")
    day = relationship("ContinentalDay")
