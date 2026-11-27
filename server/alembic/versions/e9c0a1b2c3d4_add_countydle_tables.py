"""Add English Countydle tables and seed the 48 ceremonial counties."""

from alembic import op
import sqlalchemy as sa

revision = "e9c0a1b2c3d4"
down_revision = "1a2b3c4d5e6f"
branch_labels = None
depends_on = None

ENGLISH_COUNTIES_SEED = [
    (1, "Bedfordshire", "East of England"),
    (2, "Berkshire", "South East"),
    (3, "Bristol", "South West"),
    (4, "Buckinghamshire", "South East"),
    (5, "Cambridgeshire", "East of England"),
    (6, "Cheshire", "North West"),
    (7, "City of London", "London"),
    (8, "Cornwall", "South West"),
    (9, "Cumbria", "North West"),
    (10, "Derbyshire", "East Midlands"),
    (11, "Devon", "South West"),
    (12, "Dorset", "South West"),
    (13, "Durham", "North East"),
    (14, "East Riding of Yorkshire", "Yorkshire and the Humber"),
    (15, "East Sussex", "South East"),
    (16, "Essex", "East of England"),
    (17, "Gloucestershire", "South West"),
    (18, "Greater London", "London"),
    (19, "Greater Manchester", "North West"),
    (20, "Hampshire", "South East"),
    (21, "Herefordshire", "West Midlands"),
    (22, "Hertfordshire", "East of England"),
    (23, "Isle of Wight", "South East"),
    (24, "Kent", "South East"),
    (25, "Lancashire", "North West"),
    (26, "Leicestershire", "East Midlands"),
    (27, "Lincolnshire", "East Midlands"),
    (28, "Merseyside", "North West"),
    (29, "Norfolk", "East of England"),
    (30, "North Yorkshire", "Yorkshire and the Humber"),
    (31, "Northamptonshire", "East Midlands"),
    (32, "Northumberland", "North East"),
    (33, "Nottinghamshire", "East Midlands"),
    (34, "Oxfordshire", "South East"),
    (35, "Rutland", "East Midlands"),
    (36, "Shropshire", "West Midlands"),
    (37, "Somerset", "South West"),
    (38, "South Yorkshire", "Yorkshire and the Humber"),
    (39, "Staffordshire", "West Midlands"),
    (40, "Suffolk", "East of England"),
    (41, "Surrey", "South East"),
    (42, "Tyne and Wear", "North East"),
    (43, "Warwickshire", "West Midlands"),
    (44, "West Midlands", "West Midlands"),
    (45, "West Sussex", "South East"),
    (46, "West Yorkshire", "Yorkshire and the Humber"),
    (47, "Wiltshire", "South West"),
    (48, "Worcestershire", "West Midlands"),
]


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "english_counties" not in existing_tables:
        op.create_table(
            "english_counties",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("name", sa.String(), nullable=False, unique=True),
            sa.Column("region", sa.String(), nullable=True),
        )

    if "countydle_days" not in existing_tables:
        op.create_table(
            "countydle_days",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("county_id", sa.Integer(), sa.ForeignKey("english_counties.id")),
            sa.Column("date", sa.Date(), nullable=False),
        )

    if "countydle_states" not in existing_tables:
        op.create_table(
            "countydle_states",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("day_id", sa.Integer(), sa.ForeignKey("countydle_days.id")),
            sa.Column("remaining_questions", sa.Integer(), nullable=False, server_default="8"),
            sa.Column("remaining_guesses", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("questions_asked", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("guesses_made", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_game_over", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("won", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
        )

    if "countydle_guesses" not in existing_tables:
        op.create_table(
            "countydle_guesses",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("day_id", sa.Integer(), sa.ForeignKey("countydle_days.id")),
            sa.Column("guess", sa.String(), nullable=False),
            sa.Column("county_id", sa.Integer(), sa.ForeignKey("english_counties.id"), nullable=True),
            sa.Column("guessed_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("answer", sa.Boolean(), nullable=True),
        )

    if "countydle_questions" not in existing_tables:
        op.create_table(
            "countydle_questions",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("day_id", sa.Integer(), sa.ForeignKey("countydle_days.id")),
            sa.Column("context", sa.String(), nullable=True),
            sa.Column("original_question", sa.String(), nullable=False),
            sa.Column("question", sa.String(), nullable=True),
            sa.Column("valid", sa.Boolean(), nullable=False),
            sa.Column("answer", sa.Boolean(), nullable=True),
            sa.Column("explanation", sa.String(), nullable=False),
            sa.Column("asked_at", sa.DateTime(), server_default=sa.func.now()),
        )

    # Idempotently seed the 48 English ceremonial counties
    for cid, name, region in ENGLISH_COUNTIES_SEED:
        bind.execute(
            sa.text(
                "INSERT INTO english_counties (id, name, region) "
                "VALUES (:id, :name, :region) "
                "ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, region = EXCLUDED.region"
            ),
            {"id": cid, "name": name, "region": region},
        )


def downgrade():
    op.drop_table("countydle_questions")
    op.drop_table("countydle_guesses")
    op.drop_table("countydle_states")
    op.drop_table("countydle_days")
    op.drop_table("english_counties")
