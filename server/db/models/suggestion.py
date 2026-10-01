from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.sql import func

from db.base import Base


class Suggestion(Base):
    __tablename__ = "suggestions"
    __table_args__ = (Index("ix_suggestions_created_at_id", "created_at", "id"),)

    id = Column(Integer, primary_key=True)
    topic = Column(String(16), nullable=False)
    message = Column(Text, nullable=False)
    name = Column(String(100), nullable=True)
    email = Column(String(254), nullable=True)
    reporter_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
