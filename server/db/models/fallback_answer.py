from sqlalchemy import Boolean, Column, Date, DateTime, Index, String, Text
from sqlalchemy.sql import func

from db.base import Base


class FallbackAnswer(Base):
    __tablename__ = "fallback_answers"
    __table_args__ = (
        Index("ix_fallback_answers_signature", "signature"),
        Index("ix_fallback_answers_game_date", "game_date"),
    )

    key = Column(String(64), primary_key=True)
    signature = Column(String(64), nullable=False)
    game_date = Column(Date, nullable=False)
    answer = Column(Boolean, nullable=False)
    explanation = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class FallbackAnswerBlock(Base):
    __tablename__ = "fallback_answer_blocks"
    __table_args__ = (Index("ix_fallback_answer_blocks_game_date", "game_date"),)

    signature = Column(String(64), primary_key=True)
    game_date = Column(Date, nullable=False)
