"""Add clarification column to regional mode question tables."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3a4b5c6d7e8f"
down_revision: Union[str, Sequence[str], None] = "2d4f6a8b0c1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("powiatdle_questions", sa.Column("clarification", sa.String(), nullable=True))
    op.add_column("us_statedle_questions", sa.Column("clarification", sa.String(), nullable=True))
    op.add_column("wojewodztwodle_questions", sa.Column("clarification", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("wojewodztwodle_questions", "clarification")
    op.drop_column("us_statedle_questions", "clarification")
    op.drop_column("powiatdle_questions", "clarification")
