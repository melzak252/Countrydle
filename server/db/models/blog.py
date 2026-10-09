from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db.base import Base


class DailyBlogPost(Base):
    __tablename__ = "daily_blog_posts"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, index=True, nullable=False)
    country_id = Column(Integer, ForeignKey("countries.id", ondelete="CASCADE"), nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    subtitle = Column(String, nullable=False)
    reading_time_minutes = Column(Integer, default=2)
    summary = Column(Text, nullable=False)
    fast_facts = Column(JSON, nullable=True)
    fun_facts = Column(JSON, nullable=False)
    deduction_masterclass = Column(JSON, nullable=True)
    content_markdown = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())
    source_links = Column(JSON, nullable=False, default=list)
    editorial_note = Column(Text, nullable=True)
    reviewed_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    ai_assisted = Column(Boolean, nullable=False, default=True)

    country = relationship("Country")
    reviewer = relationship("User", foreign_keys=[reviewed_by_id])

    @property
    def editorial_status(self) -> str:
        if self.reviewed_by_id is not None and self.reviewed_at is not None and self.reviewer is not None:
            return "reviewed"
        return "unreviewed"
