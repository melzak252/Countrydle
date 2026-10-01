"""Attribute Countrydle questions and guesses to guest browser identities."""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("countrydle_questions", sa.Column("guest_id", sa.String(length=36), nullable=True))
    op.add_column("countrydle_guesses", sa.Column("guest_id", sa.String(length=36), nullable=True))
    op.create_index(
        "ix_countrydle_questions_guest_day", "countrydle_questions", ["guest_id", "day_id"]
    )
    op.create_index(
        "ix_countrydle_guesses_guest_day", "countrydle_guesses", ["guest_id", "day_id"]
    )


def downgrade():
    op.drop_index("ix_countrydle_guesses_guest_day", table_name="countrydle_guesses")
    op.drop_index("ix_countrydle_questions_guest_day", table_name="countrydle_questions")
    op.drop_column("countrydle_guesses", "guest_id")
    op.drop_column("countrydle_questions", "guest_id")
