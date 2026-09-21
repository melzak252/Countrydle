from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from db.base import Base


class AnswerReport(Base):
    __tablename__ = "answer_reports"
    __table_args__ = (
        UniqueConstraint("mode", "question_id", name="uq_answer_reports_mode_question"),
        Index("ix_answer_reports_reviewed_created", "reviewed_at", "created_at", "id"),
        Index("ix_answer_reports_mode_created", "mode", "created_at", "id"),
    )

    id = Column(Integer, primary_key=True)
    mode = Column(String(32), nullable=False)
    question_id = Column(Integer, nullable=False)
    reporter_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    comment = Column(Text, nullable=False)
    details = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    reviewed_at = Column(DateTime, nullable=True)
