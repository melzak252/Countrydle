"""add_server_version_to_countrydle_questions

Revision ID: 1f2e3d4c5b6a
Revises: e84b8ed81126
Create Date: 2026-05-12 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1f2e3d4c5b6a"
down_revision: Union[str, Sequence[str], None] = "e84b8ed81126"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "countrydle_questions",
        sa.Column("server_version", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("countrydle_questions", "server_version")
