from datetime import date, datetime
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, JSON, String, Text
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

    country = relationship("Country")
