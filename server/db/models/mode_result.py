from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.orm import relationship

from db.base import Base


class ModeResultRecord(Base):
    """Generic persisted result record for modes without dedicated state tables."""

    __tablename__ = "mode_result_records"
    __table_args__ = (
        Index(
            "uq_mode_result_daily_user",
            "mode",
            "date",
            "user_id",
            unique=True,
            postgresql_where=text("date IS NOT NULL AND user_id IS NOT NULL"),
        ),
        Index(
            "uq_mode_result_daily_guest",
            "mode",
            "date",
            "guest_id",
            unique=True,
            postgresql_where=text("date IS NOT NULL AND user_id IS NULL AND guest_id IS NOT NULL"),
        ),
        Index("ix_mode_result_mode_date", "mode", "date"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    mode = Column(String(64), nullable=False, index=True)
    date = Column(Date, nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    guest_id = Column(String(36), nullable=True, index=True)
    completed = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    won = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    points = Column(Integer, nullable=False, default=0, server_default="0")
    questions_used = Column(Integer, nullable=True)
    guesses_used = Column(Integer, nullable=True)
    score = Column(Integer, nullable=True)
    max_score = Column(Integer, nullable=True)
    elapsed_seconds = Column(Float, nullable=True)
    completed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    user = relationship("User")
