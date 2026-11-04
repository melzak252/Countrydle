"""Persist ranked daily heraldry without changing legacy game histories."""
from alembic import op
import sqlalchemy as sa

revision = "h2e3a4b5c6d7"
down_revision = "h1e2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "heraldry_daily_sessions",
        sa.Column("replaced_session_id", sa.String(36), unique=True),
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("guest_id", sa.String(36)),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("target_name", sa.String(200), nullable=False),
        sa.Column("guesses", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("won", sa.Boolean(), nullable=False),
        sa.Column("points", sa.Integer()),
    )
    op.create_index("ix_heraldry_daily_sessions_date", "heraldry_daily_sessions", ["date"])
    op.create_index("uq_heraldry_daily_user_date", "heraldry_daily_sessions", ["user_id", "date"], unique=True, postgresql_where=sa.text("user_id IS NOT NULL"))
    op.create_index("uq_heraldry_daily_guest_date", "heraldry_daily_sessions", ["guest_id", "date"], unique=True, postgresql_where=sa.text("user_id IS NULL AND guest_id IS NOT NULL"))


def downgrade():
    op.drop_index("uq_heraldry_daily_guest_date", table_name="heraldry_daily_sessions")
    op.drop_index("uq_heraldry_daily_user_date", table_name="heraldry_daily_sessions")
    op.drop_index("ix_heraldry_daily_sessions_date", table_name="heraldry_daily_sessions")
    op.drop_table("heraldry_daily_sessions")
