"""Add generic mode_result_records table for unified stats and leaderboards."""
from alembic import op
import sqlalchemy as sa

revision = "2b3c4d5e6f7a"
down_revision = "1a2b3c4d5e6f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mode_result_records",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("mode", sa.String(length=64), nullable=False),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("guest_id", sa.String(length=36), nullable=True),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("won", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("questions_used", sa.Integer(), nullable=True),
        sa.Column("guesses_used", sa.Integer(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("max_score", sa.Integer(), nullable=True),
        sa.Column("elapsed_seconds", sa.Float(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_mode_result_records_mode", "mode_result_records", ["mode"])
    op.create_index("ix_mode_result_records_date", "mode_result_records", ["date"])
    op.create_index("ix_mode_result_records_user_id", "mode_result_records", ["user_id"])
    op.create_index("ix_mode_result_records_guest_id", "mode_result_records", ["guest_id"])
    op.create_index("ix_mode_result_mode_date", "mode_result_records", ["mode", "date"])
    op.create_index(
        "uq_mode_result_daily_user",
        "mode_result_records",
        ["mode", "date", "user_id"],
        unique=True,
        postgresql_where=sa.text("date IS NOT NULL AND user_id IS NOT NULL"),
    )
    op.create_index(
        "uq_mode_result_daily_guest",
        "mode_result_records",
        ["mode", "date", "guest_id"],
        unique=True,
        postgresql_where=sa.text("date IS NOT NULL AND user_id IS NULL AND guest_id IS NOT NULL"),
    )


def downgrade():
    op.drop_index("uq_mode_result_daily_guest", table_name="mode_result_records")
    op.drop_index("uq_mode_result_daily_user", table_name="mode_result_records")
    op.drop_index("ix_mode_result_mode_date", table_name="mode_result_records")
    op.drop_index("ix_mode_result_records_guest_id", table_name="mode_result_records")
    op.drop_index("ix_mode_result_records_user_id", table_name="mode_result_records")
    op.drop_index("ix_mode_result_records_date", table_name="mode_result_records")
    op.drop_index("ix_mode_result_records_mode", table_name="mode_result_records")
    op.drop_table("mode_result_records")
