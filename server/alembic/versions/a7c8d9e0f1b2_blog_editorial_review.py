"""Persist source provenance and genuine editorial review attribution.

Revision ID: a7c8d9e0f1b2
Revises: c9d0e1f2a3b4
"""
from alembic import op
import sqlalchemy as sa

revision = "a7c8d9e0f1b2"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("daily_blog_posts", sa.Column(
        "source_links", sa.JSON(), nullable=False, server_default=sa.text("'[]'"),
    ))
    op.add_column("daily_blog_posts", sa.Column("editorial_note", sa.Text(), nullable=True))
    op.add_column("daily_blog_posts", sa.Column("reviewed_by_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_daily_blog_posts_reviewed_by_id_users", "daily_blog_posts", "users",
        ["reviewed_by_id"], ["id"], ondelete="SET NULL",
    )
    op.add_column("daily_blog_posts", sa.Column(
        "reviewed_at", sa.DateTime(timezone=True), nullable=True,
    ))
    op.add_column("daily_blog_posts", sa.Column(
        "updated_at", sa.DateTime(timezone=True), nullable=True,
    ))
    # Legacy created_at is a naive UTC timestamp. Do not invent source links or
    # human reviews; unchanged articles retain their actual creation timestamp.
    op.execute(sa.text("""
        UPDATE daily_blog_posts
        SET updated_at = COALESCE(created_at AT TIME ZONE 'UTC', CURRENT_TIMESTAMP)
    """))
    op.alter_column(
        "daily_blog_posts", "updated_at", nullable=False,
        server_default=sa.func.now(), existing_type=sa.DateTime(timezone=True),
    )
    op.add_column("daily_blog_posts", sa.Column(
        "ai_assisted", sa.Boolean(), nullable=False, server_default=sa.true(),
    ))


def downgrade() -> None:
    op.drop_constraint(
        "fk_daily_blog_posts_reviewed_by_id_users", "daily_blog_posts", type_="foreignkey",
    )
    for column in (
        "ai_assisted", "updated_at", "reviewed_at", "reviewed_by_id",
        "editorial_note", "source_links",
    ):
        op.drop_column("daily_blog_posts", column)
