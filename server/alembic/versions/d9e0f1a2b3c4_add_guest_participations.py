"""Record identifiable guest activity and question-only Flagdle participation."""
from alembic import op
import sqlalchemy as sa

revision = "d9e0f1a2b3c4"
down_revision = "c8d9e0f1a2b3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "guest_participations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("guest_id", sa.String(36), nullable=False),
        sa.Column("mode", sa.String(64), nullable=False),
        sa.Column("day_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("questions_asked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("guesses_made", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("won", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("mode", "day_id", "guest_id", name="uq_guest_participation_mode_day_identity"),
    )
    op.add_column("flagdle_states", sa.Column("questions_asked", sa.Integer(), nullable=False, server_default="0"))
    # Old anonymous guesses have no browser identity; intentionally no participant backfill.


def downgrade():
    op.drop_column("flagdle_states", "questions_asked")
    op.drop_table("guest_participations")
