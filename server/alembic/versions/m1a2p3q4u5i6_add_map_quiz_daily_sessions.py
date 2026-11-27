"""Add map_quiz_daily_sessions table for 10-per-day regional map quizzes."""
from alembic import op
import sqlalchemy as sa

revision = "m1a2p3q4u5i6"
down_revision = "2b3c4d5e6f7a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "map_quiz_daily_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("replaced_session_id", sa.String(36), unique=True, nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("guest_id", sa.String(36), nullable=True),
        sa.Column("targets", sa.JSON(), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("points", sa.Integer(), nullable=True),
    )
    op.create_index("ix_map_quiz_daily_sessions_date", "map_quiz_daily_sessions", ["date"])
    op.create_index(
        "uq_map_quiz_daily_user_date",
        "map_quiz_daily_sessions",
        ["user_id", "date", "scope"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )
    op.create_index(
        "uq_map_quiz_daily_guest_date",
        "map_quiz_daily_sessions",
        ["guest_id", "date", "scope"],
        unique=True,
        postgresql_where=sa.text("user_id IS NULL AND guest_id IS NOT NULL"),
    )


def downgrade():
    op.drop_index("uq_map_quiz_daily_guest_date", table_name="map_quiz_daily_sessions")
    op.drop_index("uq_map_quiz_daily_user_date", table_name="map_quiz_daily_sessions")
    op.drop_index("ix_map_quiz_daily_sessions_date", table_name="map_quiz_daily_sessions")
    op.drop_table("map_quiz_daily_sessions")
