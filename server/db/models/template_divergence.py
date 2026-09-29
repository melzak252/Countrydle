from sqlalchemy import Column, DateTime, Index, Integer, JSON, String, Text
from sqlalchemy.sql import func

from db.base import Base


class TemplateDivergence(Base):
    __tablename__ = "template_divergences"
    __table_args__ = (
        Index("ix_template_divergences_reviewed_created", "reviewed_at", "created_at", "id"),
        Index("ix_template_divergences_mode_created", "mode", "created_at", "id"),
    )

    id = Column(Integer, primary_key=True)
    mode = Column(String(32), nullable=False)
    question = Column(Text, nullable=False)
    template_plan = Column(JSON, nullable=False)
    gemini_plan = Column(JSON, nullable=True)
    divergence_type = Column(String(64), nullable=False)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
