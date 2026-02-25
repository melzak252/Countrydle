"""allow_null_question_user_ids_for_guests

Revision ID: 7c0f0e9f6b34
Revises: d8765268ed25
Create Date: 2026-02-24 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7c0f0e9f6b34"
down_revision: Union[str, Sequence[str], None] = "d8765268ed25"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "countrydle_questions", "user_id", existing_type=sa.Integer(), nullable=True
    )
    op.alter_column(
        "powiatdle_questions", "user_id", existing_type=sa.Integer(), nullable=True
    )
    op.alter_column(
        "us_statedle_questions", "user_id", existing_type=sa.Integer(), nullable=True
    )
    op.alter_column(
        "wojewodztwodle_questions", "user_id", existing_type=sa.Integer(), nullable=True
    )


def downgrade() -> None:
    op.alter_column(
        "wojewodztwodle_questions",
        "user_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.alter_column(
        "us_statedle_questions", "user_id", existing_type=sa.Integer(), nullable=False
    )
    op.alter_column(
        "powiatdle_questions", "user_id", existing_type=sa.Integer(), nullable=False
    )
    op.alter_column(
        "countrydle_questions", "user_id", existing_type=sa.Integer(), nullable=False
    )
