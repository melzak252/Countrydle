from uuid import uuid4

from sqlalchemy import CheckConstraint, Column, DateTime, Float, ForeignKey, Integer, String, func

from db.base import Base


class QuizRun(Base):
    __tablename__ = 'heraldry_quiz_runs'
    __table_args__ = (
        CheckConstraint("status IN ('started', 'completed', 'given_up')", name='ck_heraldry_quiz_run_status'),
        CheckConstraint('(user_id IS NULL) <> (guest_id IS NULL)', name='ck_heraldry_quiz_run_owner'),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)
    guest_id = Column(String(36), nullable=True, index=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(16), nullable=False, server_default='started')
    symbol_mode = Column(String(16), nullable=False, server_default='coat')
    entity_scope = Column(String(32), nullable=False, default='county', server_default='county')
    elapsed_seconds = Column(Float, nullable=True)
    solved_count = Column(Integer, nullable=False, server_default='0')
    result_hash = Column(String(64), nullable=True)


class QuizSolve(Base):
    __tablename__ = 'heraldry_quiz_solves'

    run_id = Column(String(36), ForeignKey('heraldry_quiz_runs.id', ondelete='CASCADE'), primary_key=True)
    powiat_id = Column(Integer, primary_key=True, index=True)
    elapsed_seconds = Column(Float, nullable=False)
