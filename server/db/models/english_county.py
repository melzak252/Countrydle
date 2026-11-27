from sqlalchemy import Column, Integer, String
from db.base import Base


class EnglishCounty(Base):
    __tablename__ = "english_counties"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    region = Column(String, nullable=True)
