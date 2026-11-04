"""Count the same saved and recovered sessions visible in admin drilldowns."""
from sqlalchemy import String, case, cast, func, literal, null, select, union_all

from admin.resolver import ADMIN_MODE_CONFIGS
from db.models.guest_participation import GuestParticipation
from db.repositories.participation import _participants


def _admin_identities(start=None, end=None):
    # Existing active participation includes the new heraldry and quiz sessions.
    active = _participants(start, end)
    branches = [select(active.c.date, active.c.mode, active.c.day_id, active.c.identity)]
    for key, cfg in ADMIN_MODE_CONFIGS.items():
        day, state, question, guess = cfg.day_model, cfg.state_model, cfg.question_model, cfg.guess_model
        mode = literal('continental:') + cast(day.continent, String) if key == 'continental' else literal(key)
        day_id = cast(day.id, String)
        filters = []
        if start is not None:
            filters.append(day.date >= start)
        if end is not None:
            filters.append(day.date <= end)
        branches.append(select(day.date, mode.label('mode'), day_id.label('day_id'),
                               (literal('user:') + cast(state.user_id, String)).label('identity'))
                        .select_from(state).join(day, day.id == state.day_id).where(state.user_id.is_not(None), *filters))
        branches.append(select(day.date, mode.label('mode'), day_id.label('day_id'),
                               (literal('guest:') + GuestParticipation.guest_id).label('identity'))
                        .select_from(GuestParticipation).join(day, day.id == GuestParticipation.day_id)
                        .where(GuestParticipation.mode == mode, GuestParticipation.user_id.is_(None), *filters))
        guest_identity = (literal('guest:') + question.guest_id) if hasattr(question, 'guest_id') else cast(null(), String)
        author = case((question.user_id.is_not(None), literal('user:') + cast(question.user_id, String)),
                      else_=guest_identity)
        branches.append(select(day.date, mode.label('mode'), day_id.label('day_id'), author.label('identity'))
                        .select_from(question).join(day, day.id == question.day_id).where(*filters))
        # Legacy anonymous guesses with no guest attribution form one opaque
        # session per puzzle, not an identified person.
        anonymous = [guess.user_id.is_(None)]
        if hasattr(guess, 'guest_id'):
            anonymous.append(guess.guest_id.is_(None))
        branches.append(select(day.date, mode.label('mode'), day_id.label('day_id'),
                               cast(null(), String).label('identity'))
                        .select_from(guess).join(day, day.id == guess.day_id).where(*anonymous, *filters))
    rows = union_all(*branches).subquery()
    return select(rows.c.date, rows.c.mode, rows.c.day_id, rows.c.identity).group_by(
        rows.c.date, rows.c.mode, rows.c.day_id, rows.c.identity
    ).subquery()


async def admin_counts(session, start=None, end=None, *, include_breakdown=True):
    identities = _admin_identities(start, end)
    totals = (await session.execute(select(
        func.count().label('sessions'), func.count(func.distinct(identities.c.identity)).label('players')
    ).select_from(identities))).one()
    if not include_breakdown:
        return totals, {}, {}
    by_date = (await session.execute(select(
        identities.c.date, func.count().label('sessions'),
        func.count(func.distinct(identities.c.identity)).label('players')
    ).group_by(identities.c.date))).all()
    by_mode_date = (await session.execute(select(
        identities.c.date, identities.c.mode, func.count().label('sessions'),
        func.count(func.distinct(identities.c.identity)).label('players')
    ).group_by(identities.c.date, identities.c.mode))).all()
    return totals, {row.date: row for row in by_date}, {(row.date, row.mode): row for row in by_mode_date}


async def admin_mode_identities(session, day, mode):
    identities = _admin_identities(day, day)
    return set((await session.execute(select(identities.c.identity).where(
        identities.c.date == day, identities.c.mode == mode
    ))).scalars().all())
