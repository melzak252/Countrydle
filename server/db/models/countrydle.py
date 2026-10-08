from passlib.context import CryptContext
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    and_,
)
from sqlalchemy.orm import relationship, foreign
from sqlalchemy.sql import func

from db.base import Base
from db.models.guess import CountrydleGuess
from db.models.question import CountrydleQuestion
from db.models.user import User


class CountrydleDay(Base):
    __tablename__ = "countrydle_days"

    id = Column(Integer, primary_key=True, index=True)
    country_id = Column(Integer, ForeignKey("countries.id"))
    date = Column(Date, nullable=False, default=func.now())

    country = relationship("Country")


class CountrydleState(Base):
    __tablename__ = "countrydle_states"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    day_id = Column(Integer, ForeignKey("countrydle_days.id"))
    remaining_questions = Column(Integer, nullable=False, default=10)
    remaining_guesses = Column(Integer, nullable=False, default=3)
    questions_asked = Column(Integer, nullable=False, default=0)
    guesses_made = Column(Integer, nullable=False, default=0)
    is_game_over = Column(Boolean, nullable=False, default=False)
    won = Column(Boolean, nullable=False, default=False)
    points = Column(Integer, nullable=False, default=0)

    user = relationship("User")
    day = relationship("CountrydleDay")
