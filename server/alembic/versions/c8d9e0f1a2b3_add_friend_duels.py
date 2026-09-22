"""Persist live human-owned friend duels and independent advisory evidence."""
from alembic import op
import sqlalchemy as sa

revision = "c8d9e0f1a2b3"
down_revision = "7a8f9e0d1c2b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "friend_matches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("invite_code", sa.String(32), nullable=False, unique=True),
        sa.Column("create_request_id", sa.String(36), nullable=False, unique=True),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("friend_matches.id", ondelete="SET NULL"), unique=True),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("phase", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("move_ordinal", sa.Integer(), nullable=False),
        sa.Column("active_player_id", sa.String(36)),
        sa.Column("pending_question_id", sa.String(36)),
        sa.Column("pending_winner_id", sa.String(36)),
        sa.Column("winner_id", sa.String(36)),
        sa.Column("result", sa.String(16)),
        sa.Column("draw_offer_by", sa.String(36)),
        sa.Column("deadline", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_friend_matches_status_deadline", "friend_matches", ["status", "deadline"])
    op.create_table(
        "friend_seats",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("match_id", sa.String(36), sa.ForeignKey("friend_matches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(40), nullable=False),
        sa.Column("credential_hash", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("join_request_id", sa.String(36), nullable=False, unique=True),
        sa.Column("secret", sa.JSON()),
        sa.Column("ready", sa.Boolean(), nullable=False),
        sa.Column("rematch_ready", sa.Boolean(), nullable=False),
        sa.Column("guess_count", sa.Integer(), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("timeout_count", sa.Integer(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("match_id", "position", name="uq_friend_seat_position"),
        sa.UniqueConstraint("match_id", "credential_hash", name="uq_friend_seat_credential"),
    )
    op.create_index("ix_friend_seats_match_id", "friend_seats", ["match_id"])
    op.create_table(
        "friend_moves",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("match_id", sa.String(36), sa.ForeignKey("friend_matches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("player_id", sa.String(36), sa.ForeignKey("friend_seats.id"), nullable=False),
        sa.Column("subject_id", sa.String(36), sa.ForeignKey("friend_seats.id"), nullable=False),
        sa.Column("question", sa.Text()),
        sa.Column("entity", sa.JSON()),
        sa.Column("target", sa.JSON()),
        sa.Column("answer", sa.String(16)),
        sa.Column("correct", sa.Boolean()),
        sa.Column("timed_out", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("revisions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True)),
        sa.Column("ai_seen_before_answer", sa.Boolean(), nullable=False),
        sa.Column("review_status", sa.String(24), nullable=False),
        sa.Column("review_note", sa.Text(), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_history", sa.JSON(), nullable=False),
        sa.UniqueConstraint("match_id", "ordinal", name="uq_friend_move_ordinal"),
    )
    op.create_index("ix_friend_moves_match_id", "friend_moves", ["match_id"])
    op.create_table(
        "friend_actions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("match_id", sa.String(36), sa.ForeignKey("friend_matches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_id", sa.String(36), nullable=False),
        sa.Column("player_id", sa.String(36), sa.ForeignKey("friend_seats.id"), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("type", sa.String(24), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("applied_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("match_id", "action_id", name="uq_friend_action_id"),
    )
    op.create_table(
        "friend_advisories",
        sa.Column("question_id", sa.String(36), sa.ForeignKey("friend_moves.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("match_id", sa.String(36), sa.ForeignKey("friend_matches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("friend_seats.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("answer", sa.String(16)),
        sa.Column("explanation", sa.Text()),
        sa.Column("source", sa.String(128)),
        sa.Column("interpretation", sa.Text()),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("attempts", sa.JSON(), nullable=False),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("late", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text()),
    )
    op.create_index("ix_friend_advisories_claim", "friend_advisories", ["status", "lease_until", "created_at"])
    op.create_table(
        "friend_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("question_id", sa.String(36), sa.ForeignKey("friend_moves.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reporter_id", sa.String(36), sa.ForeignKey("friend_seats.id"), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("question_id", "reporter_id", name="uq_friend_report_author"),
    )


def downgrade():
    for table in ("friend_reports", "friend_advisories", "friend_actions", "friend_moves", "friend_seats", "friend_matches"):
        op.drop_table(table)
