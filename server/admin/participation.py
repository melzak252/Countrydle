"""Preserve legacy session totals and count only identified active participants."""
from collections import defaultdict
from types import SimpleNamespace
from sqlalchemy import String, case, cast, literal, null, or_, select, union_all

from admin.resolver import ADMIN_MODE_CONFIGS
from db.models.guest_participation import GuestParticipation
from db.repositories.participation import _participants


async def _fetch_linked_guests(session):
    rows = (await session.execute(
        select(GuestParticipation.mode, GuestParticipation.day_id, GuestParticipation.guest_id).where(
            GuestParticipation.user_id.is_not(None),
            or_(GuestParticipation.questions_asked > 0, GuestParticipation.guesses_made > 0),
        )
    )).all()
    return {(mode, str(day_id), guest_id) for mode, day_id, guest_id in rows if guest_id}


def _build_identity_rows_query(start=None, end=None, include_anonymous=True):
    """Build a single UNION ALL + GROUP BY query without correlated NOT EXISTS subplans."""
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
        branches.append(
            select(day.date, mode.label('mode'), day_id.label('day_id'), question_identity.label('identity'))
            .select_from(question)
            .join(day, day.id == question.day_id)
            .where(question.valid.is_(True), question.answer.is_not(None), question_identity.is_not(None), *filters)
        )

        guest_guess_identity = (
            literal('guest:') + guess.guest_id
            if hasattr(guess, 'guest_id') else cast(null(), String)
        )
        guess_identity = case(
            (guess.user_id.is_not(None), literal('user:') + cast(guess.user_id, String)),
            else_=guest_guess_identity,
        )
        guess_filters = [guess.answer.is_not(None)]
        if not include_anonymous:
            guess_filters.append(guess_identity.is_not(None))
        branches.append(
            select(day.date, mode.label('mode'), day_id.label('day_id'), guess_identity.label('identity'))
            .select_from(guess)
            .join(day, day.id == guess.day_id)
            .where(*guess_filters, *filters)
        )

    rows = union_all(*branches).subquery()
    return select(rows.c.date, rows.c.mode, rows.c.day_id, rows.c.identity).group_by(
        rows.c.date, rows.c.mode, rows.c.day_id, rows.c.identity
    )


def _summarize_rows(rows, include_breakdown=True):
    total_sessions = len(rows)
    total_players = len({ident for _, _, _, ident in rows if ident is not None})
    totals = SimpleNamespace(sessions=total_sessions, players=total_players)
    if not include_breakdown:
        return totals, {}, {}

    day_sessions = defaultdict(int)
    day_players = defaultdict(set)
    mode_sessions = defaultdict(int)
    mode_players = defaultdict(set)
    for d, m, _, ident in rows:
        day_sessions[d] += 1
        mode_sessions[(d, m)] += 1
        if ident is not None:
            day_players[d].add(ident)
            mode_players[(d, m)].add(ident)

    by_date = {
        d: SimpleNamespace(date=d, sessions=day_sessions[d], players=len(day_players[d]))
        for d in day_sessions
    }
    by_mode_date = {
        (d, m): SimpleNamespace(date=d, mode=m, sessions=mode_sessions[(d, m)], players=len(mode_players[(d, m)]))
        for (d, m) in mode_sessions
    }
    return totals, by_date, by_mode_date


async def _load_filtered_rows(session, start=None, end=None, include_anonymous=True):
    linked_guests = await _fetch_linked_guests(session)
    raw_rows = (await session.execute(_build_identity_rows_query(start, end, include_anonymous=include_anonymous))).all()
    filtered = []
    for d, m, did, ident in raw_rows:
        if ident is not None and ident.startswith('guest:') and (m, did, ident[6:]) in linked_guests:
            continue
        filtered.append((d, m, did, ident))
    return filtered


async def admin_counts(session, start=None, end=None, *, include_breakdown=True):
    rows = await _load_filtered_rows(session, start, end, include_anonymous=True)
    return _summarize_rows(rows, include_breakdown=include_breakdown)


async def admin_overview_counts(session, recent_start, recent_end):
    """Compute both all-time totals and recent-window breakdown from a single DB scan."""
    all_rows = await _load_filtered_rows(session, include_anonymous=True)
    all_time, _, _ = _summarize_rows(all_rows, include_breakdown=False)
    recent_rows = [row for row in all_rows if recent_start <= row[0] <= recent_end]
    _, by_date, by_mode_date = _summarize_rows(recent_rows, include_breakdown=True)
    return all_time, by_date, by_mode_date


async def admin_mode_identities(session, day, mode):
    rows = await _load_filtered_rows(session, day, day, include_anonymous=False)
    return {ident for d, m, _, ident in rows if d == day and m == mode and ident is not None}
