from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f1e2d3c4b5a6"
down_revision: Union[str, Sequence[str], None] = "e0f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "patch_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("version", name="uq_patch_notes_version"),
        sa.CheckConstraint("length(trim(title)) BETWEEN 1 AND 200", name="ck_patch_notes_title"),
        sa.CheckConstraint("length(trim(body)) BETWEEN 1 AND 20000", name="ck_patch_notes_body"),
    )
    op.create_index("ix_patch_notes_published_at_id", "patch_notes", ["published_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_patch_notes_published_at_id", table_name="patch_notes")
    op.drop_table("patch_notes")
