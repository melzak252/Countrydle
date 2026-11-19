"""Preserve legacy session totals and count only identified active participants."""
from sqlalchemy import String, case, cast, func, literal, null, or_, select, union, union_all

from admin.resolver import ADMIN_MODE_CONFIGS
from db.models.guest_participation import GuestParticipation
from db.repositories.participation import _participants


def _admin_identities(start=None, end=None):
    """Count only active gameplay sessions (no empty page-opens, no double-counted synced guests)."""
    active = _admin_active_identities(start, end)
    branches = [select(active.c.date, active.c.mode, active.c.day_id, active.c.identity)]
    for key, cfg in ADMIN_MODE_CONFIGS.items():
        day, guess = cfg.day_model, cfg.guess_model
        mode = literal('continental:') + cast(day.continent, String) if key == 'continental' else literal(key)
        day_id = cast(day.id, String)
        filters = []
        if start is not None:
            filters.append(day.date >= start)
        if end is not None:
            filters.append(day.date <= end)
        # Legacy anonymous guesses with no user or guest attribution still count as 1 session per puzzle.
        anonymous = [guess.user_id.is_(None), guess.answer.is_not(None)]
        if hasattr(guess, 'guest_id'):
            anonymous.append(guess.guest_id.is_(None))
        branches.append(
            select(day.date, mode.label('mode'), day_id.label('day_id'), cast(null(), String).label('identity'))
            .select_from(guess).join(day, day.id == guess.day_id).where(*anonymous, *filters)
        )
    rows = union_all(*branches).subquery()
    return select(rows.c.date, rows.c.mode, rows.c.day_id, rows.c.identity).group_by(
        rows.c.date, rows.c.mode, rows.c.day_id, rows.c.identity
    ).subquery()


def _admin_active_identities(start=None, end=None):
    """Count active identified IDs, recovering saved daily actions without state rows."""
    active = _participants(start, end)
    branches = [
        select(active.c.date, active.c.mode, active.c.day_id, active.c.identity)
        .where(active.c.identity.is_not(None))
    ]
    for key, cfg in ADMIN_MODE_CONFIGS.items():
        day = cfg.day_model
        question = cfg.question_model
        guess = cfg.guess_model
        mode = literal('continental:') + cast(day.continent, String) if key == 'continental' else literal(key)
        day_id = cast(day.id, String)
        filters = []
        if start is not None:
            filters.append(day.date >= start)
        if end is not None:
            filters.append(day.date <= end)

        linked_identity = literal('user:') + cast(GuestParticipation.user_id, String)
        branches.append(
            select(day.date, mode.label('mode'), day_id.label('day_id'), linked_identity.label('identity'))
            .select_from(GuestParticipation)
            .join(day, day.id == GuestParticipation.day_id)
            .where(
                GuestParticipation.mode == mode,
                GuestParticipation.user_id.is_not(None),
                or_(GuestParticipation.questions_asked > 0, GuestParticipation.guesses_made > 0),
                *filters,
            )
        )

        guest_identity = (
            literal('guest:') + question.guest_id
            if hasattr(question, 'guest_id') else cast(null(), String)
        )
        question_identity = case(
            (question.user_id.is_not(None), literal('user:') + cast(question.user_id, String)),
            else_=guest_identity,
        )
        question_filters = [
            question.valid.is_(True),
            question.answer.is_not(None),
            question_identity.is_not(None),
        ]
        if hasattr(question, 'guest_id'):
            linked_guest = select(GuestParticipation.id).where(
                GuestParticipation.guest_id == question.guest_id,
                GuestParticipation.mode == mode,
                GuestParticipation.day_id == question.day_id,
                GuestParticipation.user_id.is_not(None),
                or_(GuestParticipation.questions_asked > 0, GuestParticipation.guesses_made > 0),
            ).exists()
            question_filters.append(
                or_(question.user_id.is_not(None), question.guest_id.is_(None), ~linked_guest)
            )
        branches.append(
            select(day.date, mode.label('mode'), day_id.label('day_id'), question_identity.label('identity'))
            .select_from(question)
            .join(day, day.id == question.day_id)
            .where(*question_filters, *filters)
        )

        guest_guess_identity = (
            literal('guest:') + guess.guest_id
            if hasattr(guess, 'guest_id') else cast(null(), String)
        )
        guess_identity = case(
            (guess.user_id.is_not(None), literal('user:') + cast(guess.user_id, String)),
            else_=guest_guess_identity,
        )
        guess_filters = [guess_identity.is_not(None), guess.answer.is_not(None)]
        if hasattr(guess, 'guest_id'):
            linked_guest = select(GuestParticipation.id).where(
                GuestParticipation.guest_id == guess.guest_id,
                GuestParticipation.mode == mode,
                GuestParticipation.day_id == guess.day_id,
                GuestParticipation.user_id.is_not(None),
                or_(GuestParticipation.questions_asked > 0, GuestParticipation.guesses_made > 0),
            ).exists()
            guess_filters.append(
                or_(guess.user_id.is_not(None), guess.guest_id.is_(None), ~linked_guest)
            )
        branches.append(
            select(day.date, mode.label('mode'), day_id.label('day_id'), guess_identity.label('identity'))
            .select_from(guess)
            .join(day, day.id == guess.day_id)
            .where(*guess_filters, *filters)
        )

    rows = union_all(*branches).subquery()
    return select(rows.c.date, rows.c.mode, rows.c.day_id, rows.c.identity).group_by(
        rows.c.date, rows.c.mode, rows.c.day_id, rows.c.identity
    ).subquery()


async def admin_counts(session, start=None, end=None, *, include_breakdown=True):
    sessions = _admin_identities(start, end)
    players = _admin_active_identities(start, end)
    totals = (await session.execute(select(
        select(func.count()).select_from(sessions).scalar_subquery().label('sessions'),
        select(func.count(func.distinct(players.c.identity)))
        .select_from(players).scalar_subquery().label('players'),
    ))).one()
    if not include_breakdown:
        return totals, {}, {}
    session_days = select(
        sessions.c.date, func.count().label('sessions')
    ).group_by(sessions.c.date).subquery()
    player_days = select(
        players.c.date, func.count(func.distinct(players.c.identity)).label('players')
    ).group_by(players.c.date).subquery()
    dates = union(select(session_days.c.date), select(player_days.c.date)).subquery()
    by_date = (await session.execute(select(
        dates.c.date, func.coalesce(session_days.c.sessions, 0).label('sessions'),
        func.coalesce(player_days.c.players, 0).label('players'),
    ).select_from(dates)
      .outerjoin(session_days, session_days.c.date == dates.c.date)
      .outerjoin(player_days, player_days.c.date == dates.c.date))).all()
    session_modes = select(
        sessions.c.date, sessions.c.mode, func.count().label('sessions')
    ).group_by(sessions.c.date, sessions.c.mode).subquery()
    player_modes = select(
        players.c.date, players.c.mode,
        func.count(func.distinct(players.c.identity)).label('players'),
    ).group_by(players.c.date, players.c.mode).subquery()
    mode_keys = union(
        select(session_modes.c.date, session_modes.c.mode),
        select(player_modes.c.date, player_modes.c.mode),
    ).subquery()
    by_mode_date = (await session.execute(select(
        mode_keys.c.date, mode_keys.c.mode,
        func.coalesce(session_modes.c.sessions, 0).label('sessions'),
        func.coalesce(player_modes.c.players, 0).label('players'),
    ).select_from(mode_keys).outerjoin(
        session_modes,
        (session_modes.c.date == mode_keys.c.date) & (session_modes.c.mode == mode_keys.c.mode),
    ).outerjoin(
        player_modes,
        (player_modes.c.date == mode_keys.c.date) & (player_modes.c.mode == mode_keys.c.mode),
    ))).all()
    return totals, {row.date: row for row in by_date}, {
        (row.date, row.mode): row for row in by_mode_date
    }




async def admin_mode_identities(session, day, mode):
    identities = _admin_active_identities(day, day)
    return set((await session.execute(select(identities.c.identity).where(
        identities.c.date == day, identities.c.mode == mode, identities.c.identity.is_not(None)
    ))).scalars().all())
