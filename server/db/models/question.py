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
    JSON,
    String,
    Text,
    and_,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db.base import Base


class CountrydleQuestion(Base):
    __tablename__ = "countrydle_questions"
    __table_args__ = (Index("ix_countrydle_questions_guest_day", "guest_id", "day_id"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    guest_id = Column(String(36), nullable=True)

    day_id = Column(Integer, ForeignKey("countrydle_days.id"))
    context = Column(String)
    original_question = Column(String, nullable=False)
    question = Column(String)
    valid = Column(Boolean, nullable=False)
    answer = Column(Boolean)
    explanation = Column(String, nullable=False)
    fact_provenance = Column(JSON, nullable=False, default=list, server_default="[]")
    server_version = Column(String, nullable=True)
    asked_at = Column(DateTime, default=func.now())

    user = relationship("User", back_populates="countrydle_questions")
    day = relationship("CountrydleDay")
