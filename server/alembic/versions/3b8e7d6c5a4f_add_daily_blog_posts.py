"""add_daily_blog_posts

Revision ID: 3b8e7d6c5a4f
Revises: 1f2e3d4c5b6a
Create Date: 2026-09-20 00:00:00.000000

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3b8e7d6c5a4f"
down_revision: Union[str, Sequence[str], None] = "1f2e3d4c5b6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "daily_blog_posts",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("date", sa.Date(), unique=True, index=True, nullable=False),
        sa.Column(
            "country_id",
            sa.Integer(),
            sa.ForeignKey("countries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(), unique=True, index=True, nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("subtitle", sa.String(), nullable=False),
        sa.Column("reading_time_minutes", sa.Integer(), default=2),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("fast_facts", sa.JSON(), nullable=True),
        sa.Column("fun_facts", sa.JSON(), nullable=False),
        sa.Column("deduction_masterclass", sa.JSON(), nullable=True),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("daily_blog_posts")
