"""Use UTC for the existing continental puzzle DATE server default.

Only the default for future inserts changes; persisted dates and targets remain
untouched. Other daily DATE columns have no server default in migration history.
"""
from alembic import op
import sqlalchemy as sa

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "continental_days",
        "date",
        existing_type=sa.Date(),
        existing_nullable=False,
        server_default=sa.func.date(sa.func.timezone("UTC", sa.func.current_timestamp())),
    )


def downgrade():
    op.alter_column(
        "continental_days",
        "date",
        existing_type=sa.Date(),
        existing_nullable=False,
        server_default=sa.func.current_date(),
    )
