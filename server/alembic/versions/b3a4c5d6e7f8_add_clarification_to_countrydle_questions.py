"""Add clarification to countrydle_questions.

Revision ID: b3a4c5d6e7f8
Revises: a7c8d9e0f1b2
Create Date: 2026-10-12 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3a4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "a7c8d9e0f1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "countrydle_questions",
        sa.Column("clarification", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("countrydle_questions", "clarification")
