from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    text,
)

from db.base import Base


class PowiatMapQuizSession(Base):
    __tablename__ = "powiat_map_quiz_sessions"
    __table_args__ = (
        CheckConstraint(
            "(user_id IS NOT NULL AND guest_id IS NULL) OR "
            "(user_id IS NULL AND guest_id IS NOT NULL)",
            name="ck_powiat_map_quiz_sessions_single_owner",
        ),
        CheckConstraint(
            "score >= 0 AND score <= 10",
            name="ck_powiat_map_quiz_sessions_score_range",
        ),
        Index(
            "uq_powiat_map_quiz_sessions_user_day",
            "date",
            "user_id",
            unique=True,
            postgresql_where=text("user_id IS NOT NULL"),
        ),
        Index(
            "uq_powiat_map_quiz_sessions_guest_day",
            "date",
            "guest_id",
            unique=True,
            postgresql_where=text("user_id IS NULL AND guest_id IS NOT NULL"),
        ),
        Index(
            "ix_powiat_map_quiz_sessions_date_completed",
            "date",
            "completed_at",
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    date = Column(Date, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    guest_id = Column(String(36), nullable=True)
    targets = Column(JSON, nullable=False)
    answers = Column(JSON, nullable=False, default=list, server_default=text("'[]'"))
    score = Column(Integer, nullable=False, default=0, server_default=text("0"))
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
