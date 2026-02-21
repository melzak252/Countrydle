from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from db.base import Base

class CountryFragment(Base):
    __tablename__ = "country_fragments"
    id = Column(Integer, primary_key=True, index=True)
    country_id = Column(Integer, ForeignKey("countries.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    embedding = Column(Vector(1536))  # OpenAI embedding size
    
    country = relationship("Country")

class PowiatFragment(Base):
    __tablename__ = "powiat_fragments"
    id = Column(Integer, primary_key=True, index=True)
    powiat_id = Column(Integer, ForeignKey("powiaty.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    embedding = Column(Vector(1536))
    
    powiat = relationship("Powiat")

class WojewodztwoFragment(Base):
    __tablename__ = "wojewodztwo_fragments"
    id = Column(Integer, primary_key=True, index=True)
    wojewodztwo_id = Column(Integer, ForeignKey("wojewodztwa.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    embedding = Column(Vector(1536))
    
    wojewodztwo = relationship("Wojewodztwo")

class USStateFragment(Base):
    __tablename__ = "us_state_fragments"
    id = Column(Integer, primary_key=True, index=True)
    us_state_id = Column(Integer, ForeignKey("us_states.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    embedding = Column(Vector(1536))
    
    us_state = relationship("USState")
