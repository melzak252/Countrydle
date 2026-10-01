"""Add general suggestions."""
from alembic import op
import sqlalchemy as sa

revision = "9f8e7d6c5b4a"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "suggestions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("topic", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("reporter_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_suggestions_created_at_id", "suggestions", ["created_at", "id"])


def downgrade():
    op.drop_index("ix_suggestions_created_at_id", table_name="suggestions")
    op.drop_table("suggestions")
