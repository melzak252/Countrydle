"""Add Kosovo and repair only unplayed current/future disabled targets.

Existing facts, past puzzles and all recorded play remain untouched. SQLite
provisioning runs at startup; the separate ingestion command populates RAG.
"""
from alembic import op
import sqlalchemy as sa

revision = "e0f1a2b3c4d5"
down_revision = "d9e0f1a2b3c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        INSERT INTO countries (name, official_name, wiki, md_file)
        SELECT 'Kosovo', 'Republic of Kosovo', 'https://en.wikipedia.org/wiki/Kosovo',
               'data/countries/Kosovo.md'
        WHERE NOT EXISTS (SELECT 1 FROM countries WHERE name = 'Kosovo')
    """))
    op.execute(sa.text("""
        UPDATE countrydle_days AS d
        SET country_id = (SELECT id FROM countries WHERE name = 'Kosovo')
        WHERE d.date >= CURRENT_DATE
          AND d.country_id IN (SELECT id FROM countries WHERE name = 'Israel')
          AND NOT EXISTS (SELECT 1 FROM countrydle_states s WHERE s.day_id = d.id)
          AND NOT EXISTS (SELECT 1 FROM countrydle_guesses g WHERE g.day_id = d.id)
          AND NOT EXISTS (SELECT 1 FROM countrydle_questions q WHERE q.day_id = d.id)
          AND NOT EXISTS (SELECT 1 FROM daily_blog_posts b WHERE b.date = d.date)
          AND NOT EXISTS (SELECT 1 FROM guest_participations p
                          WHERE p.mode = 'countrydle' AND p.day_id = d.id)
    """))
    op.execute(sa.text("""
        UPDATE flagdle_days AS d
        SET country_id = (SELECT id FROM countries WHERE name = 'Kosovo')
        WHERE d.date >= CURRENT_DATE
          AND d.country_id IN (SELECT id FROM countries WHERE name = 'Israel')
          AND NOT EXISTS (SELECT 1 FROM flagdle_states s WHERE s.day_id = d.id)
          AND NOT EXISTS (SELECT 1 FROM flagdle_guesses g WHERE g.day_id = d.id)
          AND NOT EXISTS (SELECT 1 FROM guest_participations p
                          WHERE p.mode = 'flagdle' AND p.day_id = d.id)
    """))
    op.execute(sa.text("""
        UPDATE continental_days AS d
        SET country_id = replacement.id
        FROM countries AS replacement
        WHERE replacement.name = CASE d.continent
              WHEN 'europe' THEN 'Kosovo'
              WHEN 'asia' THEN 'Japan'
              WHEN 'africa' THEN 'Kenya'
              WHEN 'americas' THEN 'Brazil'
            END
          AND d.date >= CURRENT_DATE
          AND (d.country_id IN (SELECT id FROM countries WHERE name = 'Israel')
               OR (d.continent = 'europe' AND d.country_id IN
                   (SELECT id FROM countries WHERE name = 'Azerbaijan')))
          AND NOT EXISTS (SELECT 1 FROM continental_states s WHERE s.day_id = d.id)
          AND NOT EXISTS (SELECT 1 FROM continental_guesses g WHERE g.day_id = d.id)
          AND NOT EXISTS (SELECT 1 FROM continental_questions q WHERE q.day_id = d.id)
          AND NOT EXISTS (SELECT 1 FROM guest_participations p
                          WHERE p.mode = 'continental:' || CAST(d.continent AS TEXT)
                            AND p.day_id = d.id)
    """))


def downgrade() -> None:
    # Additive country data may already be referenced by games and audit records.
    # Restoring disabled targets or deleting Kosovo would corrupt that history.
    pass
