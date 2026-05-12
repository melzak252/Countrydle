from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db.base import Base


class CountryFactChangeLog(Base):
    __tablename__ = "country_fact_change_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    game_type = Column(String, nullable=False, default="countrydle")
    entity_id = Column(Integer, nullable=False)
    entity_name = Column(String, nullable=False)
    country_id = Column(Integer, nullable=False)
    country_name = Column(String, nullable=False)
    relation = Column(String, nullable=False)
    operation = Column(String, nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    sqlite_table = Column(String, nullable=False)
    sqlite_column = Column(String, nullable=False)
    note = Column(Text, nullable=True)
    server_version = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    user = relationship("User", back_populates="country_fact_change_logs")
