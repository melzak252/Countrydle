"""Add persisted daily Powiat map quiz sessions."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2d4f6a8b0c1e"
down_revision: Union[str, Sequence[str], None] = "1a2b3c4d5e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "powiat_map_quiz_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("guest_id", sa.String(length=36), nullable=True),
        sa.Column("targets", sa.JSON(), nullable=False),
        sa.Column("answers", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("score", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(user_id IS NOT NULL AND guest_id IS NULL) OR "
            "(user_id IS NULL AND guest_id IS NOT NULL)",
            name="ck_powiat_map_quiz_sessions_single_owner",
        ),
        sa.CheckConstraint(
            "score >= 0 AND score <= 10",
            name="ck_powiat_map_quiz_sessions_score_range",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_powiat_map_quiz_sessions_user_day",
        "powiat_map_quiz_sessions",
        ["date", "user_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )
    op.create_index(
        "uq_powiat_map_quiz_sessions_guest_day",
        "powiat_map_quiz_sessions",
        ["date", "guest_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NULL AND guest_id IS NOT NULL"),
    )
    op.create_index(
        "ix_powiat_map_quiz_sessions_date_completed",
        "powiat_map_quiz_sessions",
        ["date", "completed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_powiat_map_quiz_sessions_date_completed",
        table_name="powiat_map_quiz_sessions",
    )
    op.drop_index(
        "uq_powiat_map_quiz_sessions_guest_day",
        table_name="powiat_map_quiz_sessions",
    )
    op.drop_index(
        "uq_powiat_map_quiz_sessions_user_day",
        table_name="powiat_map_quiz_sessions",
    )
    op.drop_table("powiat_map_quiz_sessions")
