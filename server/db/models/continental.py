from datetime import date
from enum import StrEnum
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship
from daily_clock import utc_today
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
    date = Column(
        Date,
        nullable=False,
        default=utc_today,
        server_default=func.date(func.timezone("UTC", func.current_timestamp())),
        index=True,
    )

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
    __table_args__ = (Index("ix_continental_guesses_guest_day", "guest_id", "day_id"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    guest_id = Column(String(36), nullable=True)
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
    __table_args__ = (Index("ix_continental_questions_guest_day", "guest_id", "day_id"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    guest_id = Column(String(36), nullable=True)
    day_id = Column(Integer, ForeignKey("continental_days.id", ondelete="CASCADE"), nullable=False, index=True)
    original_question = Column(String, nullable=False)
    question = Column(String, nullable=True)
    valid = Column(Boolean, nullable=False)
    answer = Column(Boolean, nullable=True)
    explanation = Column(String, nullable=True)
    context = Column(String, nullable=True)
    fact_provenance = Column(JSON, nullable=False, default=list, server_default="[]")
    asked_at = Column(DateTime, server_default=func.now(), nullable=False)

    user = relationship("User")
    day = relationship("ContinentalDay")
