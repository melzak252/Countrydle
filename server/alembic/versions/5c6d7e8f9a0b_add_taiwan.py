"""Add Taiwan to the countries catalog.

Existing facts, past puzzles and all recorded play remain untouched. SQLite
provisioning runs at startup; `python -m scripts.country_additions` populates
PostgreSQL fragments and Qdrant embeddings.
"""
from alembic import op
import sqlalchemy as sa

revision = "5c6d7e8f9a0b"
down_revision = "4b5c6d7e8f9a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        INSERT INTO countries (name, official_name, wiki, md_file)
        SELECT 'Taiwan', 'Republic of China', 'https://en.wikipedia.org/wiki/Taiwan',
               'data/countries/Taiwan.md'
        WHERE NOT EXISTS (SELECT 1 FROM countries WHERE name = 'Taiwan')
    """))


def downgrade() -> None:
    # Additive country data may already be referenced by games and audit records.
    pass
