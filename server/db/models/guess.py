from passlib.context import CryptContext
from pgvector.sqlalchemy import Vector
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
    and_,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db.base import Base


class CountrydleGuess(Base):
    __tablename__ = "countrydle_guesses"
    __table_args__ = (Index("ix_countrydle_guesses_guest_day", "guest_id", "day_id"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    guest_id = Column(String(36), nullable=True)

    day_id = Column(Integer, ForeignKey("countrydle_days.id"))
    guess = Column(String, nullable=False)
    guessed_at = Column(DateTime, default=func.now())
    answer = Column(Boolean)

    user = relationship("User", back_populates="countrydle_guesses")
    day = relationship("CountrydleDay")
