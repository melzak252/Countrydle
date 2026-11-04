from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, JSON, String, text

from db.base import Base


class HeraldryDailySession(Base):
    __tablename__ = "heraldry_daily_sessions"
    __table_args__ = (
        Index("uq_heraldry_daily_user_date", "user_id", "date", unique=True,
              postgresql_where=text("user_id IS NOT NULL")),
        Index("uq_heraldry_daily_guest_date", "guest_id", "date", unique=True,
              postgresql_where=text("user_id IS NULL AND guest_id IS NOT NULL")),
    )

    id = Column(String(36), primary_key=True)
    replaced_session_id = Column(String(36), unique=True, nullable=True)
    date = Column(Date, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    guest_id = Column(String(36), nullable=True)
    target_id = Column(Integer, nullable=False)
    target_name = Column(String(200), nullable=False)
    guesses = Column(JSON, nullable=False, default=list)
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    won = Column(Boolean, nullable=False, default=False)
    points = Column(Integer, nullable=True)
