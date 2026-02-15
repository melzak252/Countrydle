from passlib.context import CryptContext
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    and_,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db.base import Base

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=True)
    email = Column(String, unique=True, nullable=False)


    hashed_password = Column(String, nullable=True)
    verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    points = relationship("UserPoints", uselist=False, back_populates="user")
    questions = relationship("Question", back_populates="user")
    permissions = relationship(
        "Permission", secondary="user_permissions", viewonly=True
    )
    guesses = relationship("Guess", back_populates="user")

    @property
    def permission_names(self):
        return [permission.name for permission in self.permissions]

    @staticmethod
    def verify_password(plain_password, hashed_password):
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def hash_password(password):
        return pwd_context.hash(password)


class UserPoints(Base):
    __tablename__ = "user_points"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    points = Column(Integer, default=0, nullable=False)
    streak = Column(Integer, default=0, nullable=False)
    longest_streak_start = Column(Date, nullable=True)
    longest_streak = Column(Integer, default=0, nullable=False)

    user = relationship("User", back_populates="points")


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)


class UserPermission(Base):
    __tablename__ = "user_permissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    permission_id = Column(Integer, ForeignKey("permissions.id"))


class AccountUpdate(Base):
    __tablename__ = "account_update"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"))

    username = Column(String, nullable=False)
    email = Column(String, nullable=False)
    added_date = Column(DateTime, default=func.now())
