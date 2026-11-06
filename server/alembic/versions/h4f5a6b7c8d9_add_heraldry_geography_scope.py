"""Isolate regional symbol history from legacy county games."""
from alembic import op
import sqlalchemy as sa

revision = "h4f5a6b7c8d9"
down_revision = "h3e4a5b6c7d8"
branch_labels = None
depends_on = None


def _indexes(scoped):
    suffix = ["entity_scope"] if scoped else []
    op.create_index("uq_heraldry_daily_user_date", "heraldry_daily_sessions",
                    ["user_id", "date", "symbol_mode", *suffix], unique=True,
                    postgresql_where=sa.text("user_id IS NOT NULL"))
    op.create_index("uq_heraldry_daily_guest_date", "heraldry_daily_sessions",
                    ["guest_id", "date", "symbol_mode", *suffix], unique=True,
                    postgresql_where=sa.text("user_id IS NULL AND guest_id IS NOT NULL"))


def _drop_indexes():
    op.drop_index("uq_heraldry_daily_user_date", table_name="heraldry_daily_sessions")
    op.drop_index("uq_heraldry_daily_guest_date", table_name="heraldry_daily_sessions")


def upgrade():
    for table in ("heraldry_daily_sessions", "heraldry_quiz_runs"):
        op.add_column(table, sa.Column("entity_scope", sa.String(32), nullable=False, server_default="county"))
    _drop_indexes()
    _indexes(True)


def downgrade():
    connection = op.get_bind()
    for table in ("heraldry_daily_sessions", "heraldry_quiz_runs"):
        if connection.execute(sa.text(
            f"SELECT EXISTS (SELECT 1 FROM {table} WHERE entity_scope <> 'county')"
        )).scalar():
            raise RuntimeError("Cannot downgrade heraldry geography scope: regional history exists.")
    _drop_indexes()
    _indexes(False)
    op.drop_column("heraldry_quiz_runs", "entity_scope")
    op.drop_column("heraldry_daily_sessions", "entity_scope")
