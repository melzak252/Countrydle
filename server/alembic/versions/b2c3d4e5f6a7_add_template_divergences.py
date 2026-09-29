from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "f1e2d3c4b5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "template_divergences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("template_plan", sa.JSON(), nullable=False),
        sa.Column("gemini_plan", sa.JSON(), nullable=True),
        sa.Column("divergence_type", sa.String(length=64), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_template_divergences_reviewed_created",
        "template_divergences",
        ["reviewed_at", "created_at", "id"],
    )
    op.create_index(
        "ix_template_divergences_mode_created",
        "template_divergences",
        ["mode", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_template_divergences_mode_created", table_name="template_divergences")
    op.drop_index("ix_template_divergences_reviewed_created", table_name="template_divergences")
    op.drop_table("template_divergences")
