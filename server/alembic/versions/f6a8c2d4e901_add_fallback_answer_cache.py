"""Add persistent fallback answer cache and report blocks."""
from alembic import op
import sqlalchemy as sa


revision = "f6a8c2d4e901"
down_revision = "9f8e7d6c5b4a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "fallback_answers",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("signature", sa.String(length=64), nullable=False),
        sa.Column("game_date", sa.Date(), nullable=False),
        sa.Column("answer", sa.Boolean(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_fallback_answers_signature", "fallback_answers", ["signature"])
    op.create_index("ix_fallback_answers_game_date", "fallback_answers", ["game_date"])
    op.create_table(
        "fallback_answer_blocks",
        sa.Column("signature", sa.String(length=64), primary_key=True),
        sa.Column("game_date", sa.Date(), nullable=False),
    )
    op.create_index("ix_fallback_answer_blocks_game_date", "fallback_answer_blocks", ["game_date"])


def downgrade():
    op.drop_index("ix_fallback_answer_blocks_game_date", table_name="fallback_answer_blocks")
    op.drop_table("fallback_answer_blocks")
    op.drop_index("ix_fallback_answers_game_date", table_name="fallback_answers")
    op.drop_index("ix_fallback_answers_signature", table_name="fallback_answers")
    op.drop_table("fallback_answers")
