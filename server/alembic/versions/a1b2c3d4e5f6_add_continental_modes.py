"""add_continental_modes

Revision ID: a1b2c3d4e5f6
Revises: 4c9f2a1b8d60
Create Date: 2026-09-22 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "4c9f2a1b8d60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "continental_days",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("continent", sa.String(length=16), nullable=False),
        sa.Column("country_id", sa.Integer(), sa.ForeignKey("countries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False, server_default=sa.func.current_date()),
        sa.UniqueConstraint("continent", "date", name="uq_continental_days_continent_date"),
    )
    op.create_index("ix_continental_days_id", "continental_days", ["id"])
    op.create_index("ix_continental_days_continent", "continental_days", ["continent"])
    op.create_index("ix_continental_days_date", "continental_days", ["date"])

    op.create_table(
        "continental_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("day_id", sa.Integer(), sa.ForeignKey("continental_days.id", ondelete="CASCADE"), nullable=False),
        sa.Column("remaining_questions", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("remaining_guesses", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("questions_asked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("guesses_made", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_game_over", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("won", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("user_id", "day_id", name="uq_continental_states_user_day"),
    )
    op.create_index("ix_continental_states_id", "continental_states", ["id"])
    op.create_index("ix_continental_states_user_id", "continental_states", ["user_id"])
    op.create_index("ix_continental_states_day_id", "continental_states", ["day_id"])

    op.create_table(
        "continental_guesses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("day_id", sa.Integer(), sa.ForeignKey("continental_days.id", ondelete="CASCADE"), nullable=False),
        sa.Column("guess", sa.String(), nullable=False),
        sa.Column("country_id", sa.Integer(), sa.ForeignKey("countries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("guessed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("answer", sa.Boolean(), nullable=False),
        sa.Column("elapsed_seconds", sa.Integer(), nullable=True),
    )
    op.create_index("ix_continental_guesses_id", "continental_guesses", ["id"])
    op.create_index("ix_continental_guesses_user_id", "continental_guesses", ["user_id"])
    op.create_index("ix_continental_guesses_day_id", "continental_guesses", ["day_id"])

    op.create_table(
        "continental_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("day_id", sa.Integer(), sa.ForeignKey("continental_days.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_question", sa.String(), nullable=False),
        sa.Column("question", sa.String(), nullable=True),
        sa.Column("valid", sa.Boolean(), nullable=False),
        sa.Column("answer", sa.Boolean(), nullable=True),
        sa.Column("explanation", sa.String(), nullable=True),
        sa.Column("context", sa.String(), nullable=True),
        sa.Column("asked_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_continental_questions_id", "continental_questions", ["id"])
    op.create_index("ix_continental_questions_user_id", "continental_questions", ["user_id"])
    op.create_index("ix_continental_questions_day_id", "continental_questions", ["day_id"])


def downgrade() -> None:
    op.drop_table("continental_questions")
    op.drop_table("continental_guesses")
    op.drop_table("continental_states")
    op.drop_table("continental_days")
