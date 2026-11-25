"""Add guest_id attribution to US Statedle questions and guesses."""

from alembic import op
import sqlalchemy as sa


revision = "4b5c6d7e8f9a"
down_revision = "3a4b5c6d7e8f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("us_statedle_questions", sa.Column("guest_id", sa.String(length=36), nullable=True))
    op.add_column("us_statedle_guesses", sa.Column("guest_id", sa.String(length=36), nullable=True))
    op.create_index(
        "ix_us_statedle_questions_guest_day", "us_statedle_questions", ["guest_id", "day_id"]
    )
    op.create_index(
        "ix_us_statedle_guesses_guest_day", "us_statedle_guesses", ["guest_id", "day_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_us_statedle_guesses_guest_day", table_name="us_statedle_guesses")
    op.drop_index("ix_us_statedle_questions_guest_day", table_name="us_statedle_questions")
    op.drop_column("us_statedle_guesses", "guest_id")
    op.drop_column("us_statedle_questions", "guest_id")
