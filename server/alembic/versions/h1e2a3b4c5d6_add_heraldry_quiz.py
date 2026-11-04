"""Record newly tracked heraldry quiz runs and solves."""
from alembic import op
import sqlalchemy as sa

revision = 'h1e2a3b4c5d6'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'heraldry_quiz_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('guest_id', sa.String(36)),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True)),
        sa.Column('status', sa.String(16), server_default='started', nullable=False),
        sa.Column('elapsed_seconds', sa.Float()),
        sa.Column('solved_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('result_hash', sa.String(64)),
        sa.CheckConstraint("status IN ('started', 'completed', 'given_up')", name='ck_heraldry_quiz_run_status'),
        sa.CheckConstraint('(user_id IS NULL) <> (guest_id IS NULL)', name='ck_heraldry_quiz_run_owner'),
    )
    op.create_index('ix_heraldry_quiz_runs_user_id', 'heraldry_quiz_runs', ['user_id'])
    op.create_index('ix_heraldry_quiz_runs_guest_id', 'heraldry_quiz_runs', ['guest_id'])
    op.create_table(
        'heraldry_quiz_solves',
        sa.Column('run_id', sa.String(36), sa.ForeignKey('heraldry_quiz_runs.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('powiat_id', sa.Integer(), primary_key=True),
        sa.Column('elapsed_seconds', sa.Float(), nullable=False),
    )
    op.create_index('ix_heraldry_quiz_solves_powiat_id', 'heraldry_quiz_solves', ['powiat_id'])


def downgrade():
    op.drop_table('heraldry_quiz_solves')
    op.drop_table('heraldry_quiz_runs')
