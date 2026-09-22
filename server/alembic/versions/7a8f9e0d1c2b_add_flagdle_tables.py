"""add_flagdle_tables

Revision ID: 7a8f9e0d1c2b
Revises: 3b8e7d6c5a4f
Create Date: 2026-09-22 00:00:00.000000

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7a8f9e0d1c2b"
down_revision: Union[str, Sequence[str], None] = "3b8e7d6c5a4f"
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "flagdle_days",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "country_id",
            sa.Integer(),
            sa.ForeignKey("countries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), unique=True, index=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "flagdle_states",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "day_id",
            sa.Integer(),
            sa.ForeignKey("flagdle_days.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("remaining_guesses", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("guesses_made", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revealed_stage", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_game_over", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("won", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("user_id", "day_id", name="uq_flagdle_user_day"),
    )

    op.create_table(
        "flagdle_guesses",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "day_id",
            sa.Integer(),
            sa.ForeignKey("flagdle_days.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "country_id",
            sa.Integer(),
            sa.ForeignKey("countries.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("guess", sa.String(), nullable=False),
        sa.Column("answer", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("distance_km", sa.Integer(), nullable=True),
        sa.Column("bearing_degrees", sa.Integer(), nullable=True),
        sa.Column("bearing_direction", sa.String(), nullable=True),
        sa.Column("bearing_arrow", sa.String(), nullable=True),
        sa.Column("matched_colors", sa.JSON(), nullable=True),
        sa.Column("missed_colors", sa.JSON(), nullable=True),
        sa.Column("remaining_colors_count", sa.Integer(), nullable=True),
        sa.Column("matched_symbols", sa.JSON(), nullable=True),
        sa.Column("revealed_tile", sa.Integer(), nullable=True),
        sa.Column("elapsed_seconds", sa.Integer(), nullable=True),
        sa.Column("guessed_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("flagdle_guesses")
    op.drop_table("flagdle_states")
    op.drop_table("flagdle_days")
