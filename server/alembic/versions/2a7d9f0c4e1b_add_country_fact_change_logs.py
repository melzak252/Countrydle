"""add_country_fact_change_logs

Revision ID: 2a7d9f0c4e1b
Revises: 1f2e3d4c5b6a
Create Date: 2026-05-12 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2a7d9f0c4e1b"
down_revision: Union[str, Sequence[str], None] = "1f2e3d4c5b6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "country_fact_change_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("game_type", sa.String(), nullable=False, server_default="countrydle"),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("entity_name", sa.String(), nullable=False),
        sa.Column("country_id", sa.Integer(), nullable=False),
        sa.Column("country_name", sa.String(), nullable=False),
        sa.Column("relation", sa.String(), nullable=False),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("sqlite_table", sa.String(), nullable=False),
        sa.Column("sqlite_column", sa.String(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("server_version", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_country_fact_change_logs_id"), "country_fact_change_logs", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_country_fact_change_logs_id"), table_name="country_fact_change_logs")
    op.drop_table("country_fact_change_logs")
