"""Attribute Continental guesses to guest browser identities."""
from alembic import op
import sqlalchemy as sa

revision = "1a2b3c4d5e6f"
down_revision = "h4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade():
    # Historical anonymous guesses cannot be reliably matched to browser identities.
    op.add_column("continental_guesses", sa.Column("guest_id", sa.String(length=36), nullable=True))
    op.create_index(
        "ix_continental_guesses_guest_day", "continental_guesses", ["guest_id", "day_id"]
    )


def downgrade():
    op.drop_index("ix_continental_guesses_guest_day", table_name="continental_guesses")
    op.drop_column("continental_guesses", "guest_id")
