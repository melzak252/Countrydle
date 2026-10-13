"""Add clarification to continental_questions.

Revision ID: c1d2e3f4a5b6
Revises: b3a4c5d6e7f8
Create Date: 2026-10-13 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "b3a4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "continental_questions",
        sa.Column("clarification", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("continental_questions", "clarification")
