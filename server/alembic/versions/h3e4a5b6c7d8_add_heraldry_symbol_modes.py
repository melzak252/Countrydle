"""Separate coat and flag daily sessions and quiz runs."""
from alembic import op
import sqlalchemy as sa

revision = "h3e4a5b6c7d8"
down_revision = "h2e3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("heraldry_daily_sessions", "heraldry_quiz_runs"):
        op.add_column(table, sa.Column("symbol_mode", sa.String(16), nullable=False, server_default="coat"))
    op.drop_index("uq_heraldry_daily_user_date", table_name="heraldry_daily_sessions")
    op.drop_index("uq_heraldry_daily_guest_date", table_name="heraldry_daily_sessions")
    op.create_index("uq_heraldry_daily_user_date", "heraldry_daily_sessions", ["user_id", "date", "symbol_mode"], unique=True, postgresql_where=sa.text("user_id IS NOT NULL"))
    op.create_index("uq_heraldry_daily_guest_date", "heraldry_daily_sessions", ["guest_id", "date", "symbol_mode"], unique=True, postgresql_where=sa.text("user_id IS NULL AND guest_id IS NOT NULL"))


def downgrade():
    connection = op.get_bind()
    for table in ("heraldry_daily_sessions", "heraldry_quiz_runs"):
        if connection.execute(sa.text(
            f"SELECT EXISTS (SELECT 1 FROM {table} WHERE symbol_mode <> 'coat')"
        )).scalar():
            raise RuntimeError(
                "Cannot downgrade heraldry symbol modes: non-coat history exists; preserve flag data."
            )
    op.drop_index("uq_heraldry_daily_user_date", table_name="heraldry_daily_sessions")
    op.drop_index("uq_heraldry_daily_guest_date", table_name="heraldry_daily_sessions")
    op.create_index("uq_heraldry_daily_user_date", "heraldry_daily_sessions", ["user_id", "date"], unique=True, postgresql_where=sa.text("user_id IS NOT NULL"))
    op.create_index("uq_heraldry_daily_guest_date", "heraldry_daily_sessions", ["guest_id", "date"], unique=True, postgresql_where=sa.text("user_id IS NULL AND guest_id IS NOT NULL"))
    op.drop_column("heraldry_quiz_runs", "symbol_mode")
    op.drop_column("heraldry_daily_sessions", "symbol_mode")
