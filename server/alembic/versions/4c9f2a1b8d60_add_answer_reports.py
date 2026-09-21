"""add_answer_reports

Revision ID: 4c9f2a1b8d60
Revises: 3b8e7d6c5a4f
Create Date: 2026-09-21 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4c9f2a1b8d60"
down_revision: Union[str, Sequence[str], None] = "3b8e7d6c5a4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "answer_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("reporter_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("mode", "question_id", name="uq_answer_reports_mode_question"),
    )
    op.create_index("ix_answer_reports_reviewed_created", "answer_reports", ["reviewed_at", "created_at", "id"])
    op.create_index("ix_answer_reports_mode_created", "answer_reports", ["mode", "created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_answer_reports_mode_created", table_name="answer_reports")
    op.drop_index("ix_answer_reports_reviewed_created", table_name="answer_reports")
    op.drop_table("answer_reports")
