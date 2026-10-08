"""Bind all daily-mode histories to durable guest identities.

Legacy anonymous rows have no provable browser owner and deliberately remain NULL.
Terminal participation is derived from existing won/counters and mode quotas, so no
counts, results, targets, or points are rewritten.
"""
from alembic import op
import sqlalchemy as sa

revision = "a7b8c9d0e1f2"
down_revision = "f6a8c2d4e901"
branch_labels = None
depends_on = None

HISTORY_TABLES = (
    "continental_guesses", "continental_questions",
    "us_statedle_guesses", "us_statedle_questions",
    "powiatdle_guesses", "powiatdle_questions",
    "wojewodztwodle_guesses", "wojewodztwodle_questions",
    "flagdle_guesses",
)
ELAPSED_TABLES = (
    "countrydle_guesses", "us_statedle_guesses", "powiatdle_guesses", "wojewodztwodle_guesses",
)


def upgrade():
    for table in HISTORY_TABLES:
        op.add_column(table, sa.Column("guest_id", sa.String(length=36), nullable=True))
        op.create_index(f"ix_{table}_guest_day", table, ["guest_id", "day_id"])
    for table in ELAPSED_TABLES:
        op.add_column(table, sa.Column("elapsed_seconds", sa.Integer(), nullable=True))


def downgrade():
    for table in reversed(ELAPSED_TABLES):
        op.drop_column(table, "elapsed_seconds")
    for table in reversed(HISTORY_TABLES):
        op.drop_index(f"ix_{table}_guest_day", table_name=table)
        op.drop_column(table, "guest_id")
