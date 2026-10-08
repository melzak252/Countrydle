"""Persist answer-used fact evidence without changing puzzle targets or old answers."""
from alembic import op
import sqlalchemy as sa

revision = "c9d0e1f2a3b4"
down_revision = "f6a8c2d4e901"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("countrydle_questions", "continental_questions"):
        op.add_column(table, sa.Column("fact_provenance", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("continental_questions", sa.Column("guest_id", sa.String(36), nullable=True))
    op.create_index("ix_continental_questions_guest_day", "continental_questions", ["guest_id", "day_id"])
    op.create_table(
        "flagdle_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("guest_id", sa.String(36)),
        sa.Column("day_id", sa.Integer(), sa.ForeignKey("flagdle_days.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_question", sa.String(), nullable=False),
        sa.Column("question", sa.String()),
        sa.Column("valid", sa.Boolean(), nullable=False),
        sa.Column("answer", sa.Boolean()),
        sa.Column("explanation", sa.String(), nullable=False),
        sa.Column("context", sa.String()),
        sa.Column("fact_provenance", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("asked_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_flagdle_questions_id", "flagdle_questions", ["id"])
    op.create_index("ix_flagdle_questions_user_id", "flagdle_questions", ["user_id"])
    op.create_index("ix_flagdle_questions_day_id", "flagdle_questions", ["day_id"])
    op.create_index("ix_flagdle_questions_guest_day", "flagdle_questions", ["guest_id", "day_id"])


def downgrade():
    op.drop_table("flagdle_questions")
    op.drop_index("ix_continental_questions_guest_day", table_name="continental_questions")
    op.drop_column("continental_questions", "guest_id")
    for table in ("continental_questions", "countrydle_questions"):
        op.drop_column(table, "fact_provenance")
