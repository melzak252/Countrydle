from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, JSON, String, text

from db.base import Base


class MapQuizDailySession(Base):
    __tablename__ = "map_quiz_daily_sessions"
    __table_args__ = (
        Index(
            "uq_map_quiz_daily_user_date",
            "user_id",
            "date",
            "scope",
            unique=True,
            postgresql_where=text("user_id IS NOT NULL"),
        ),
        Index(
            "uq_map_quiz_daily_guest_date",
            "guest_id",
            "date",
            "scope",
            unique=True,
            postgresql_where=text("user_id IS NULL AND guest_id IS NOT NULL"),
        ),
    )

    id = Column(String(36), primary_key=True)
    replaced_session_id = Column(String(36), unique=True, nullable=True)
    date = Column(Date, nullable=False, index=True)
    scope = Column(String(32), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    guest_id = Column(String(36), nullable=True)
    targets = Column(JSON, nullable=False, default=list)
    answers = Column(JSON, nullable=False, default=list)
    score = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    points = Column(Integer, nullable=True)
