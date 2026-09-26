from sqlalchemy import CheckConstraint, Column, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from db.base import Base


class PatchNote(Base):
    __tablename__ = "patch_notes"
    __table_args__ = (
        UniqueConstraint("version", name="uq_patch_notes_version"),
        CheckConstraint("length(trim(title)) BETWEEN 1 AND 200", name="ck_patch_notes_title"),
        CheckConstraint("length(trim(body)) BETWEEN 1 AND 20000", name="ck_patch_notes_body"),
        Index("ix_patch_notes_published_at_id", "published_at", "id"),
    )

    id = Column(Integer, primary_key=True)
    version = Column(String(32), nullable=False)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
