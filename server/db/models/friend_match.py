from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint

from db.base import Base


class FriendMatch(Base):
    __tablename__ = "friend_matches"
    __table_args__ = (Index("ix_friend_matches_status_deadline", "status", "deadline"),)

    id = Column(String(36), primary_key=True)
    invite_code = Column(String(32), nullable=False, unique=True)
    create_request_id = Column(String(36), nullable=False, unique=True)
    parent_id = Column(String(36), ForeignKey("friend_matches.id", ondelete="SET NULL"), nullable=True, unique=True)
    mode = Column(String(32), nullable=False)
    status = Column(String(16), nullable=False, default="lobby")
    phase = Column(String(16), nullable=False, default="lobby")
    version = Column(Integer, nullable=False, default=1)
    turn = Column(Integer, nullable=False, default=0)
    move_ordinal = Column(Integer, nullable=False, default=0)
    active_player_id = Column(String(36), nullable=True)
    pending_question_id = Column(String(36), nullable=True)
    pending_winner_id = Column(String(36), nullable=True)
    winner_id = Column(String(36), nullable=True)
    result = Column(String(16), nullable=True)
    draw_offer_by = Column(String(36), nullable=True)
    deadline = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)


class FriendSeat(Base):
    __tablename__ = "friend_seats"
    __table_args__ = (
        UniqueConstraint("match_id", "position", name="uq_friend_seat_position"),
        UniqueConstraint("match_id", "credential_hash", name="uq_friend_seat_credential"),
    )

    id = Column(String(36), primary_key=True)
    match_id = Column(String(36), ForeignKey("friend_matches.id", ondelete="CASCADE"), nullable=False, index=True)
    position = Column(Integer, nullable=False)
    name = Column(String(40), nullable=False)
    credential_hash = Column(String(64), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    join_request_id = Column(String(36), nullable=False, unique=True)
    secret = Column(JSON, nullable=True)
    ready = Column(Boolean, nullable=False, default=False)
    rematch_ready = Column(Boolean, nullable=False, default=False)
    guess_count = Column(Integer, nullable=False, default=0)
    question_count = Column(Integer, nullable=False, default=0)
    timeout_count = Column(Integer, nullable=False, default=0)
    last_seen_at = Column(DateTime(timezone=True), nullable=False)


class FriendMove(Base):
    __tablename__ = "friend_moves"
    __table_args__ = (UniqueConstraint("match_id", "ordinal", name="uq_friend_move_ordinal"),)

    id = Column(String(36), primary_key=True)
    match_id = Column(String(36), ForeignKey("friend_matches.id", ondelete="CASCADE"), nullable=False, index=True)
    ordinal = Column(Integer, nullable=False)
    type = Column(String(16), nullable=False)
    player_id = Column(String(36), ForeignKey("friend_seats.id"), nullable=False)
    subject_id = Column(String(36), ForeignKey("friend_seats.id"), nullable=False)
    question = Column(Text, nullable=True)
    entity = Column(JSON, nullable=True)
    target = Column(JSON, nullable=True)
    answer = Column(String(16), nullable=True)
    correct = Column(Boolean, nullable=True)
    timed_out = Column(Boolean, nullable=False, default=False)
    revision = Column(Integer, nullable=False, default=1)
    revisions = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False)
    answered_at = Column(DateTime(timezone=True), nullable=True)
    ai_seen_before_answer = Column(Boolean, nullable=False, default=False)
    review_status = Column(String(24), nullable=False, default="new")
    review_note = Column(Text, nullable=False, default="")
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_history = Column(JSON, nullable=False, default=list)


class FriendAction(Base):
    __tablename__ = "friend_actions"
    __table_args__ = (UniqueConstraint("match_id", "action_id", name="uq_friend_action_id"),)

    id = Column(String(36), primary_key=True)
    match_id = Column(String(36), ForeignKey("friend_matches.id", ondelete="CASCADE"), nullable=False)
    action_id = Column(String(36), nullable=False)
    player_id = Column(String(36), ForeignKey("friend_seats.id"), nullable=False)
    payload_hash = Column(String(64), nullable=False)
    type = Column(String(24), nullable=False)
    payload = Column(JSON, nullable=False)
    applied_version = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


class FriendAdvisory(Base):
    __tablename__ = "friend_advisories"
    __table_args__ = (Index("ix_friend_advisories_claim", "status", "lease_until", "created_at"),)

    question_id = Column(String(36), ForeignKey("friend_moves.id", ondelete="CASCADE"), primary_key=True)
    match_id = Column(String(36), ForeignKey("friend_matches.id", ondelete="CASCADE"), nullable=False)
    owner_id = Column(String(36), ForeignKey("friend_seats.id"), nullable=False)
    status = Column(String(16), nullable=False, default="pending")
    answer = Column(String(16), nullable=True)
    explanation = Column(Text, nullable=True)
    source = Column(String(128), nullable=True)
    interpretation = Column(Text, nullable=True)
    evidence = Column(JSON, nullable=False, default=dict)
    attempts = Column(JSON, nullable=False, default=list)
    lease_token = Column(String(36), nullable=True)
    lease_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    late = Column(Boolean, nullable=False, default=False)
    error = Column(Text, nullable=True)


class FriendReport(Base):
    __tablename__ = "friend_reports"
    __table_args__ = (UniqueConstraint("question_id", "reporter_id", name="uq_friend_report_author"),)

    id = Column(String(36), primary_key=True)
    question_id = Column(String(36), ForeignKey("friend_moves.id", ondelete="CASCADE"), nullable=False)
    reporter_id = Column(String(36), ForeignKey("friend_seats.id"), nullable=False)
    comment = Column(Text, nullable=False)
    details = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
