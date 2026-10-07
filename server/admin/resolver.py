from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import HTTPException, status
from sqlalchemy import (
    String,
    JSON,
    cast,
    and_,
    case,
    desc,
    distinct,
    func,
    literal,
    or_,
    select,
    union_all,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from daily_clock import utc_today
from db.models.answer_report import AnswerReport
from db.models.continental import ContinentalDay, ContinentalGuess, ContinentalQuestion, ContinentalState
from db.models.country import Country
from db.models.countrydle import CountrydleDay, CountrydleState
from db.models.guess import CountrydleGuess
from db.models.flagdle import FlagdleDay, FlagdleGuess, FlagdleQuestion, FlagdleState
from db.models.guest_participation import GuestParticipation
from db.models.powiat import Powiat
from db.models.powiatdle import PowiatdleDay, PowiatdleGuess, PowiatdleQuestion, PowiatdleState
from db.models.question import CountrydleQuestion
from db.models.us_state import USState
from db.models.us_statedle import USStatedleDay, USStatedleGuess, USStatedleQuestion, USStatedleState
from db.models.user import User
from db.models.wojewodztwo import Wojewodztwo
from db.models.wojewodztwodle import WojewodztwodleDay, WojewodztwodleGuess, WojewodztwodleQuestion, WojewodztwodleState
from schemas.admin import (
    AdminGameSessionItem,
    AdminGameSessionTimelineEvent,
    AdminQuestionItem,
    AdminQuestionSource,
    AdminTargetStrategyStats,
    AdminTopGuessStat,
    AdminTopQuestionStat,
)


@dataclass(frozen=True)
class AdminModeConfig:
    mode_key: str
    display_name: str
    question_model: Any
    guess_model: Any
    day_model: Any
    state_model: Any
    target_model: Any
    target_fk_col: Any
    target_name_col: Any
    target_subtitle_col: Any
    default_subtitle: str
    max_questions: int | None
    max_guesses: int


ADMIN_MODE_CONFIGS: dict[str, AdminModeConfig] = {
    "countrydle": AdminModeConfig(
        mode_key="countrydle",
        display_name="World Countries",
        question_model=CountrydleQuestion,
        guess_model=CountrydleGuess,
        day_model=CountrydleDay,
        state_model=CountrydleState,
        target_model=Country,
        target_fk_col=CountrydleDay.country_id,
        target_name_col=Country.name,
        target_subtitle_col=None,
        default_subtitle="Country",
        max_questions=10,
        max_guesses=3,
    ),
    "powiatdle": AdminModeConfig(
        mode_key="powiatdle",
        display_name="Polish Counties",
        question_model=PowiatdleQuestion,
        guess_model=PowiatdleGuess,
        day_model=PowiatdleDay,
        state_model=PowiatdleState,
        target_model=Powiat,
        target_fk_col=PowiatdleDay.powiat_id,
        target_name_col=Powiat.nazwa,
        target_subtitle_col=None,
        default_subtitle="Powiat",
        max_questions=15,
        max_guesses=3,
    ),
    "us_statedle": AdminModeConfig(
        mode_key="us_statedle",
        display_name="US States",
        question_model=USStatedleQuestion,
        guess_model=USStatedleGuess,
        day_model=USStatedleDay,
        state_model=USStatedleState,
        target_model=USState,
        target_fk_col=USStatedleDay.us_state_id,
        target_name_col=USState.name,
        target_subtitle_col=USState.code,
        default_subtitle="US State",
        max_questions=8,
        max_guesses=3,
    ),
    "wojewodztwodle": AdminModeConfig(
        mode_key="wojewodztwodle",
        display_name="Polish Voivodeships",
        question_model=WojewodztwodleQuestion,
        guess_model=WojewodztwodleGuess,
        day_model=WojewodztwodleDay,
        state_model=WojewodztwodleState,
        target_model=Wojewodztwo,
        target_fk_col=WojewodztwodleDay.wojewodztwo_id,
        target_name_col=Wojewodztwo.nazwa,
        target_subtitle_col=None,
        default_subtitle="Województwo",
        max_questions=5,
        max_guesses=2,
    ),
    "continental": AdminModeConfig(
        mode_key="continental",
        display_name="Continental",
        question_model=ContinentalQuestion,
        guess_model=ContinentalGuess,
        day_model=ContinentalDay,
        state_model=ContinentalState,
        target_model=Country,
        target_fk_col=ContinentalDay.country_id,
        target_name_col=Country.name,
        target_subtitle_col=ContinentalDay.continent,
        default_subtitle="Continental",
        max_questions=8,
        max_guesses=3,
    ),
    "flagdle": AdminModeConfig(
        mode_key="flagdle", display_name="Flags",
        question_model=FlagdleQuestion, guess_model=FlagdleGuess,
        day_model=FlagdleDay, state_model=FlagdleState,
        target_model=Country, target_fk_col=FlagdleDay.country_id,
        target_name_col=Country.name, target_subtitle_col=None,
        default_subtitle="Country", max_questions=None, max_guesses=12,
    ),
}


def classify_question_source(
    valid: bool, context: Optional[str]
) -> Tuple[AdminQuestionSource, Optional[str]]:
    """Classifies question answering engine and extracts KB relation if applicable."""
    if not valid or context == "local_planner:invalid":
        return "invalid", None

    if context:
        if context.startswith("local_kb:") or context.startswith("flag_kb:"):
            parts = context.split(":", 1)
            relation = parts[1].strip() if len(parts) > 1 else None
            return "local_kb", relation
        elif context.startswith("local_planner:"):
            parts = context.split(":", 1)
            relation = parts[1].strip() if len(parts) > 1 else None
            return "local_kb", relation
        else:
            return "fallback", None

    return "local_kb" if valid else "invalid", None


def _build_mode_question_query(
    cfg: AdminModeConfig,
    search: Optional[str],
    date_filter: Optional[date],
    source_filter: Optional[str],
    answer_filter: Optional[str],
    target_name_filter: Optional[str],
    has_report_filter: Optional[bool],
):
    col_q_id = cfg.question_model.id.label("id")
    col_mode = literal(cfg.mode_key).label("mode")
    col_day_id = cfg.question_model.day_id.label("day_id")
    col_game_date = cfg.day_model.date.label("game_date")
    col_target_id = cfg.target_model.id.label("target_id")
    col_target_name = cfg.target_name_col.label("target_name")
    col_target_subtitle = (
        func.cast(cfg.target_subtitle_col, String).label("target_subtitle")
        if cfg.target_subtitle_col is not None
        else literal(cfg.default_subtitle).label("target_subtitle")
    )
    col_user_id = cfg.question_model.user_id.label("user_id")
    col_username = User.username.label("username")
    col_guest_id = (
        cfg.question_model.guest_id.label("guest_id")
        if hasattr(cfg.question_model, "guest_id")
        else literal(None, type_=String).label("guest_id")
    )
    col_original_question = cfg.question_model.original_question.label("original_question")
    col_question = (
        cfg.question_model.question.label("question")
        if hasattr(cfg.question_model, "question")
        else literal(None, type_=String).label("question")
    )
    col_valid = cfg.question_model.valid.label("valid")
    col_answer = cfg.question_model.answer.label("answer")
    col_explanation = cfg.question_model.explanation.label("explanation")
    col_context = cfg.question_model.context.label("context")
    col_asked_at = cfg.question_model.asked_at.label("asked_at")
    col_fact_provenance = (
        cfg.question_model.fact_provenance if hasattr(cfg.question_model, "fact_provenance")
        else cast(literal(None), JSON)
    ).label("fact_provenance")
    col_report_id = AnswerReport.id.label("report_id")

    where_clauses = []

    if date_filter:
        where_clauses.append(cfg.day_model.date == date_filter)

    if target_name_filter and target_name_filter.strip():
        where_clauses.append(cfg.target_name_col.ilike(f"%{target_name_filter.strip()}%"))

    if search and search.strip():
        pattern = f"%{search.strip()}%"
        search_conds = [
            cfg.question_model.original_question.ilike(pattern),
            cfg.question_model.explanation.ilike(pattern),
            cfg.target_name_col.ilike(pattern),
            User.username.ilike(pattern),
        ]
        if hasattr(cfg.question_model, "question"):
            search_conds.append(cfg.question_model.question.ilike(pattern))
        where_clauses.append(or_(*search_conds))

    if answer_filter:
        ans_lower = answer_filter.lower().strip()
        if ans_lower == "yes":
            where_clauses.append(and_(cfg.question_model.valid == True, cfg.question_model.answer == True))
        elif ans_lower == "no":
            where_clauses.append(and_(cfg.question_model.valid == True, cfg.question_model.answer == False))
        elif ans_lower == "invalid":
            where_clauses.append(cfg.question_model.valid == False)

    if source_filter:
        src_lower = source_filter.lower().strip()
        if src_lower == "local_kb":
            where_clauses.append(
                and_(
                    cfg.question_model.valid == True,
                    or_(
                        cfg.question_model.context.like("local_kb:%"),
                        cfg.question_model.context.like("flag_kb:%"),
                        cfg.question_model.context.like("local_planner:%"),
                    ),
                    cfg.question_model.context != "local_planner:invalid",
                )
            )
        elif src_lower == "fallback":
            where_clauses.append(
                and_(
                    cfg.question_model.valid == True,
                    cfg.question_model.context.isnot(None),
                    ~cfg.question_model.context.like("local_kb:%"),
                    ~cfg.question_model.context.like("flag_kb:%"),
                    ~cfg.question_model.context.like("local_planner:%"),
                )
            )
        elif src_lower == "invalid":
            where_clauses.append(
                or_(
                    cfg.question_model.valid == False,
                    cfg.question_model.context == "local_planner:invalid",
                )
            )

    if has_report_filter is True:
        where_clauses.append(AnswerReport.id.isnot(None))
    elif has_report_filter is False:
        where_clauses.append(AnswerReport.id.is_(None))

    stmt = (
        select(
            col_q_id,
            col_mode,
            col_day_id,
            col_game_date,
            col_target_id,
            col_target_name,
            col_target_subtitle,
            col_user_id,
            col_username,
            col_guest_id,
            col_original_question,
            col_question,
            col_valid,
            col_answer,
            col_explanation,
            col_context,
            col_asked_at,
            col_report_id,
            col_fact_provenance,
        )
        .join(cfg.day_model, cfg.question_model.day_id == cfg.day_model.id)
        .join(cfg.target_model, cfg.target_fk_col == cfg.target_model.id)
        .outerjoin(User, cfg.question_model.user_id == User.id)
        .outerjoin(
            AnswerReport,
            and_(
                AnswerReport.mode == cfg.mode_key,
                AnswerReport.question_id == cfg.question_model.id,
            ),
        )
    )

    if where_clauses:
        stmt = stmt.where(and_(*where_clauses))

    return stmt


async def query_admin_questions(
    session: AsyncSession,
    mode: Optional[str] = None,
    search: Optional[str] = None,
    date_filter: Optional[date] = None,
    source_filter: Optional[str] = None,
    answer_filter: Optional[str] = None,
    target_name_filter: Optional[str] = None,
    has_report_filter: Optional[bool] = None,
    page: int = 1,
    limit: int = 30,
) -> Tuple[List[AdminQuestionItem], int]:
    normalized_mode = mode.lower().strip() if mode else None
    if normalized_mode and normalized_mode.startswith("continental"):
        normalized_mode = "continental"

    if normalized_mode and normalized_mode in ADMIN_MODE_CONFIGS:
        cfg = ADMIN_MODE_CONFIGS[normalized_mode]
        query = _build_mode_question_query(
            cfg,
            search=search,
            date_filter=date_filter,
            source_filter=source_filter,
            answer_filter=answer_filter,
            target_name_filter=target_name_filter,
            has_report_filter=has_report_filter,
        )
        count_stmt = select(func.count()).select_from(query.subquery())
        total = (await session.execute(count_stmt)).scalar() or 0
        data_stmt = (
            query.order_by(desc(cfg.question_model.asked_at), desc(cfg.question_model.id))
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await session.execute(data_stmt)
        rows = result.all()
    else:
        # Union all 5 modes
        queries = [
            _build_mode_question_query(
                cfg,
                search=search,
                date_filter=date_filter,
                source_filter=source_filter,
                answer_filter=answer_filter,
                target_name_filter=target_name_filter,
                has_report_filter=has_report_filter,
            )
            for cfg in ADMIN_MODE_CONFIGS.values()
        ]
        union_subq = union_all(*queries).subquery()
        count_stmt = select(func.count()).select_from(union_subq)
        total = (await session.execute(count_stmt)).scalar() or 0
        data_stmt = (
            select(union_subq)
            .order_by(desc(union_subq.c.asked_at), desc(union_subq.c.id))
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await session.execute(data_stmt)
        rows = result.all()

    items = []
    for r in rows:
        is_guest = r.user_id is None
        username = r.username
        if not username:
            username = f"Guest {r.guest_id[:8]}" if r.guest_id else "Guest"

        src, rel = classify_question_source(r.valid, r.context)
        items.append(
            AdminQuestionItem(
                id=r.id,
                mode=r.mode,
                day_id=r.day_id,
                game_date=r.game_date.isoformat() if hasattr(r.game_date, "isoformat") else str(r.game_date),
                target_id=r.target_id,
                target_name=r.target_name,
                target_subtitle=str(r.target_subtitle) if r.target_subtitle else None,
                user_id=r.user_id,
                username=username,
                is_guest=is_guest,
                original_question=r.original_question,
                question=r.question,
                valid=r.valid,
                answer=r.answer,
                explanation=r.explanation or "",
                context=r.context,
                source=src,
                relation=rel,
                asked_at=r.asked_at,
                has_report=r.report_id is not None,
                report_id=r.report_id,
                fact_provenance=getattr(r, "fact_provenance", None) or [],
            )
        )

    return items, total


async def _resolve_day_and_target(
    session: AsyncSession,
    cfg: AdminModeConfig,
    target_date: date,
    mode_raw: str,
) -> Tuple[Any, str, str]:
    day_stmt = select(cfg.day_model).where(cfg.day_model.date == target_date)
    if cfg.mode_key == "continental":
        continent_val = mode_raw.split(":", 1)[1] if ":" in mode_raw else "europe"
        day_stmt = day_stmt.where(cfg.day_model.continent == continent_val)

    day = (await session.execute(day_stmt)).scalars().first()
    if not day:
        return None, "Unknown", cfg.default_subtitle

    target_fk = getattr(day, cfg.target_fk_col.key)
    target = (await session.execute(select(cfg.target_model).where(cfg.target_model.id == target_fk))).scalars().first()
    target_name = getattr(target, cfg.target_name_col.key, "Unknown")

    if cfg.target_subtitle_col is not None:
        sub_raw = getattr(day, cfg.target_subtitle_col.key) if hasattr(day, cfg.target_subtitle_col.key) else getattr(target, cfg.target_subtitle_col.key, None)
        target_subtitle = str(sub_raw.value if hasattr(sub_raw, "value") else sub_raw) if sub_raw else cfg.default_subtitle
    else:
        target_subtitle = cfg.default_subtitle

    return day, target_name, target_subtitle


async def query_admin_game_sessions(
    session: AsyncSession,
    mode: str = "countrydle",
    target_date: Optional[date] = None,
    status_filter: Optional[str] = None,
    player_type_filter: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> Tuple[List[AdminGameSessionItem], int]:
    clean_mode = mode.lower().strip()
    mode_key = clean_mode.split(":", 1)[0]
    cfg = ADMIN_MODE_CONFIGS.get(mode_key, ADMIN_MODE_CONFIGS["countrydle"])

    if not target_date:
        target_date = utc_today()

    day, target_name, target_subtitle = await _resolve_day_and_target(session, cfg, target_date, clean_mode)
    if not day:
        return [], 0

    candidates = []
    seen_identities: Set[Tuple[str, Any]] = set()

    # 1. Registered users from State
    if player_type_filter != "guest":
        states_stmt = (
            select(cfg.state_model)
            .options(joinedload(cfg.state_model.user))
            .where(cfg.state_model.day_id == day.id)
        )
        states = (await session.execute(states_stmt)).scalars().all()
        for st in states:
            if st.user_id and ("user", st.user_id) not in seen_identities:
                seen_identities.add(("user", st.user_id))
                st_status = "won" if st.won else ("lost" if st.is_game_over else "in_progress")
                candidates.append({
                    "is_guest": False,
                    "user_id": st.user_id,
                    "guest_id": None,
                    "username": st.user.username if st.user else f"User #{st.user_id}",
                    "initial_status": st_status,
                })

        # Extra registered users with questions on this day
        extra_users_stmt = (
            select(cfg.question_model.user_id, User.username)
            .distinct()
            .join(User, cfg.question_model.user_id == User.id)
            .where(cfg.question_model.day_id == day.id)
        )
        extra_users = (await session.execute(extra_users_stmt)).all()
        for u_id, u_name in extra_users:
            if u_id and ("user", u_id) not in seen_identities:
                seen_identities.add(("user", u_id))
                candidates.append({
                    "is_guest": False,
                    "user_id": u_id,
                    "guest_id": None,
                    "username": u_name or f"User #{u_id}",
                    "initial_status": "in_progress",
                })

    # 2. Guests from GuestParticipation
    if player_type_filter != "registered":
        gp_stmt = select(GuestParticipation).where(
            GuestParticipation.mode == cfg.mode_key,
            GuestParticipation.day_id == day.id,
        )
        gp_rows = (await session.execute(gp_stmt)).scalars().all()
        for gp in gp_rows:
            if gp.guest_id and ("guest", gp.guest_id) not in seen_identities:
                seen_identities.add(("guest", gp.guest_id))
                gp_status = (
                    "won"
                    if gp.won
                    else ("lost" if (gp.guesses_made >= cfg.max_guesses or (cfg.max_questions is not None and gp.questions_asked >= cfg.max_questions)) else "in_progress")
                )
                candidates.append({
                    "is_guest": True,
                    "user_id": None,
                    "guest_id": gp.guest_id,
                    "username": f"Guest {gp.guest_id[:8]}",
                    "initial_status": gp_status,
                })

        # Extra guests with questions
        if hasattr(cfg.question_model, "guest_id"):
            extra_g_stmt = (
                select(cfg.question_model.guest_id)
                .distinct()
                .where(
                    cfg.question_model.day_id == day.id,
                    cfg.question_model.user_id.is_(None),
                    cfg.question_model.guest_id.isnot(None),
                )
            )
            extra_guests = (await session.execute(extra_g_stmt)).scalars().all()
            for g_id in extra_guests:
                if g_id and ("guest", g_id) not in seen_identities:
                    seen_identities.add(("guest", g_id))
                    candidates.append({
                        "is_guest": True,
                        "user_id": None,
                        "guest_id": g_id,
                        "username": f"Guest {g_id[:8]}",
                        "initial_status": "in_progress",
                    })

        # Anonymous legacy rows
        anon_where = [
            cfg.question_model.day_id == day.id,
            cfg.question_model.user_id.is_(None),
        ]
        if hasattr(cfg.question_model, "guest_id"):
            anon_where.append(cfg.question_model.guest_id.is_(None))
        anon_count = (await session.execute(select(func.count(cfg.question_model.id)).where(and_(*anon_where)))).scalar() or 0
        if anon_count > 0 and ("guest", "anonymous") not in seen_identities:
            seen_identities.add(("guest", "anonymous"))
            candidates.append({
                "is_guest": True,
                "user_id": None,
                "guest_id": "anonymous",
                "username": "Anonymous Guest",
                "initial_status": "in_progress",
            })

    if status_filter:
        stat_filter_lower = status_filter.lower().strip()
        candidates = [c for c in candidates if c["initial_status"] == stat_filter_lower]

    total_sessions = len(candidates)
    page_candidates = candidates[(page - 1) * limit : page * limit]

    sessions: List[AdminGameSessionItem] = []
    for c in page_candidates:
        sess_id = f"user-{c['user_id']}-day-{day.id}" if c["user_id"] else f"guest-{c['guest_id']}-day-{day.id}"

        # Fetch questions
        q_where = [cfg.question_model.day_id == day.id]
        if c["user_id"]:
            q_where.append(cfg.question_model.user_id == c["user_id"])
        elif c["guest_id"] and c["guest_id"] != "anonymous" and hasattr(cfg.question_model, "guest_id"):
            q_where.append(cfg.question_model.guest_id == c["guest_id"])
        else:
            q_where.append(cfg.question_model.user_id.is_(None))
            if hasattr(cfg.question_model, "guest_id"):
                q_where.append(cfg.question_model.guest_id.is_(None))

        q_stmt = select(cfg.question_model).where(and_(*q_where)).order_by(cfg.question_model.id.asc())
        q_rows = (await session.execute(q_stmt)).scalars().all()

        # Fetch guesses
        g_where = [cfg.guess_model.day_id == day.id]
        if c["user_id"]:
            g_where.append(cfg.guess_model.user_id == c["user_id"])
        elif c["guest_id"] and c["guest_id"] != "anonymous" and hasattr(cfg.guess_model, "guest_id"):
            g_where.append(cfg.guess_model.guest_id == c["guest_id"])
        else:
            g_where.append(cfg.guess_model.user_id.is_(None))
            if hasattr(cfg.guess_model, "guest_id"):
                g_where.append(cfg.guess_model.guest_id.is_(None))

        g_stmt = select(cfg.guess_model).where(and_(*g_where)).order_by(cfg.guess_model.id.asc())
        g_rows = (await session.execute(g_stmt)).scalars().all()

        timeline: List[AdminGameSessionTimelineEvent] = []
        for q in q_rows:
            src, rel = classify_question_source(q.valid, q.context)
            timeline.append(
                AdminGameSessionTimelineEvent(
                    event_type="question",
                    id=q.id,
                    timestamp=q.asked_at,
                    question=getattr(q, "question", None) or q.original_question,
                    original_question=q.original_question,
                    valid=q.valid,
                    answer=q.answer,
                    explanation=q.explanation,
                    source=src,
                    relation=rel,
                    context=q.context,
                )
            )

        for g in g_rows:
            timeline.append(
                AdminGameSessionTimelineEvent(
                    event_type="guess",
                    id=g.id,
                    timestamp=g.guessed_at,
                    guess=g.guess,
                    correct=bool(g.answer),
                )
            )

        timeline.sort(key=lambda ev: (ev.timestamp or datetime.min, 0 if ev.event_type == "question" else 1, ev.id))

        has_won = any(ev.correct is True for ev in timeline)
        guesses_count = len([ev for ev in timeline if ev.event_type == "guess"])
        questions_count = len([ev for ev in timeline if ev.event_type == "question"])

        if has_won:
            final_status = "won"
        elif guesses_count >= cfg.max_guesses or (c["initial_status"] == "lost"):
            final_status = "lost"
        elif c["initial_status"] in ("won", "lost"):
            final_status = c["initial_status"]
        else:
            final_status = "in_progress"

        started_at = timeline[0].timestamp if timeline else None
        completed_at = timeline[-1].timestamp if timeline and final_status in ("won", "lost") else None
        duration_seconds = None
        if started_at and completed_at:
            duration_seconds = max(0, int((completed_at - started_at).total_seconds()))
        elif started_at and len(timeline) > 1 and timeline[-1].timestamp:
            duration_seconds = max(0, int((timeline[-1].timestamp - started_at).total_seconds()))

        sessions.append(
            AdminGameSessionItem(
                session_id=sess_id,
                mode=cfg.mode_key,
                day_id=day.id,
                game_date=day.date.isoformat(),
                target_name=target_name,
                target_subtitle=target_subtitle,
                user_id=c["user_id"],
                username=c["username"],
                is_guest=c["is_guest"],
                status=final_status,
                questions_asked=questions_count,
                guesses_made=guesses_count,
                duration_seconds=duration_seconds,
                started_at=started_at,
                completed_at=completed_at,
                timeline=timeline,
            )
        )

    return sessions, total_sessions


async def query_admin_target_stats(
    session: AsyncSession,
    mode: str = "countrydle",
    target_date: Optional[date] = None,
) -> AdminTargetStrategyStats:
    clean_mode = mode.lower().strip()
    mode_key = clean_mode.split(":", 1)[0]
    cfg = ADMIN_MODE_CONFIGS.get(mode_key, ADMIN_MODE_CONFIGS["countrydle"])

    if not target_date:
        target_date = utc_today()

    day, target_name, target_subtitle = await _resolve_day_and_target(session, cfg, target_date, clean_mode)
    if not day:
        return AdminTargetStrategyStats(
            target_name="Unknown",
            target_subtitle=cfg.default_subtitle,
            game_date=target_date.isoformat(),
            total_players=0,
            win_rate_pct=0.0,
            top_questions=[],
            top_guesses=[],
            avg_questions_winners=0.0,
            avg_questions_losers=0.0,
        )

    # 1. Fetch questions on this day
    q_stmt = select(cfg.question_model).where(cfg.question_model.day_id == day.id)
    q_rows = (await session.execute(q_stmt)).scalars().all()

    # 2. Fetch guesses on this day
    g_stmt = select(cfg.guess_model).where(cfg.guess_model.day_id == day.id)
    g_rows = (await session.execute(g_stmt)).scalars().all()

    # 3. Collect winning players
    winning_users = set(
        (
            await session.execute(
                select(cfg.state_model.user_id).where(cfg.state_model.day_id == day.id, cfg.state_model.won == True)
            )
        )
        .scalars()
        .all()
    )
    winning_guests = set(
        (
            await session.execute(
                select(GuestParticipation.guest_id).where(
                    GuestParticipation.mode == cfg.mode_key,
                    GuestParticipation.day_id == day.id,
                    GuestParticipation.won == True,
                )
            )
        )
        .scalars()
        .all()
    )

    for g in g_rows:
        if g.answer:
            if g.user_id:
                winning_users.add(g.user_id)
            if hasattr(g, "guest_id") and g.guest_id:
                winning_guests.add(g.guest_id)

    # 4. Total players
    all_users = set(q.user_id for q in q_rows if q.user_id) | set(g.user_id for g in g_rows if g.user_id)
    all_guests = set(getattr(q, "guest_id", None) for q in q_rows if getattr(q, "guest_id", None)) | set(
        getattr(g, "guest_id", None) for g in g_rows if getattr(g, "guest_id", None)
    )
    total_players = len(all_users) + len(all_guests)
    total_winners = len(all_users & winning_users) + len(all_guests & winning_guests)
    win_rate_pct = round((total_winners / max(1, total_players)) * 100, 1) if total_players > 0 else 0.0

    # 5. Top Questions
    q_groups: Dict[str, Dict[str, Any]] = {}
    player_q_counts: Dict[Tuple[str, Any], int] = {}

    for q in q_rows:
        txt = (q.original_question or getattr(q, "question", "") or "").strip()
        if not txt:
            continue
        if txt not in q_groups:
            q_groups[txt] = {"count": 0, "yes_count": 0, "askers": set()}
        q_groups[txt]["count"] += 1
        if q.valid and q.answer is True:
            q_groups[txt]["yes_count"] += 1

        asker_key = None
        if q.user_id:
            asker_key = ("user", q.user_id)
        elif hasattr(q, "guest_id") and q.guest_id:
            asker_key = ("guest", q.guest_id)

        if asker_key:
            q_groups[txt]["askers"].add(asker_key)
            player_q_counts[asker_key] = player_q_counts.get(asker_key, 0) + 1

    top_questions: List[AdminTopQuestionStat] = []
    for txt, data in sorted(q_groups.items(), key=lambda x: x[1]["count"], reverse=True)[:10]:
        yes_pct = round((data["yes_count"] / max(1, data["count"])) * 100, 1)
        winning_askers = [
            a
            for a in data["askers"]
            if (a[0] == "user" and a[1] in winning_users) or (a[0] == "guest" and a[1] in winning_guests)
        ]
        win_corr = round((len(winning_askers) / max(1, len(data["askers"]))) * 100, 1) if data["askers"] else 0.0
        top_questions.append(
            AdminTopQuestionStat(
                text=txt,
                count=data["count"],
                yes_pct=yes_pct,
                win_correlation=win_corr,
            )
        )

    # 6. Top Guesses
    g_groups: Dict[str, Dict[str, Any]] = {}
    for g in g_rows:
        txt = (g.guess or "").strip()
        if not txt:
            continue
        if txt not in g_groups:
            g_groups[txt] = {"count": 0, "correct_count": 0}
        g_groups[txt]["count"] += 1
        if g.answer:
            g_groups[txt]["correct_count"] += 1

    top_guesses: List[AdminTopGuessStat] = []
    for txt, data in sorted(g_groups.items(), key=lambda x: x[1]["count"], reverse=True)[:10]:
        correct_pct = round((data["correct_count"] / max(1, data["count"])) * 100, 1)
        top_guesses.append(
            AdminTopGuessStat(
                guess=txt,
                count=data["count"],
                correct_pct=correct_pct,
            )
        )

    # 7. Avg questions for winners vs losers
    winner_counts = [
        cnt
        for key, cnt in player_q_counts.items()
        if (key[0] == "user" and key[1] in winning_users) or (key[0] == "guest" and key[1] in winning_guests)
    ]
    loser_counts = [
        cnt
        for key, cnt in player_q_counts.items()
        if not ((key[0] == "user" and key[1] in winning_users) or (key[0] == "guest" and key[1] in winning_guests))
    ]
    avg_win = round(sum(winner_counts) / len(winner_counts), 1) if winner_counts else 0.0
    avg_loss = round(sum(loser_counts) / len(loser_counts), 1) if loser_counts else 0.0

    return AdminTargetStrategyStats(
        target_name=target_name,
        target_subtitle=target_subtitle,
        game_date=day.date.isoformat(),
        total_players=total_players,
        win_rate_pct=win_rate_pct,
        top_questions=top_questions,
        top_guesses=top_guesses,
        avg_questions_winners=avg_win,
        avg_questions_losers=avg_loss,
    )


async def invalidate_question_fallback(
    session: AsyncSession,
    mode: str,
    question_id: int,
) -> Tuple[bool, str]:
    mode_key = "countrydle" if mode.startswith("continental") else mode.lower().strip()
    if mode_key not in ADMIN_MODE_CONFIGS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported mode: {mode}",
        )
    cfg = ADMIN_MODE_CONFIGS[mode_key]
    q_stmt = select(cfg.question_model).where(cfg.question_model.id == question_id)
    question = (await session.execute(q_stmt)).scalars().first()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question #{question_id} not found in mode {mode}",
        )

    src, _ = classify_question_source(question.valid, question.context)
    if src != "fallback":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question was not answered by AI fallback (it is answered by local KB or invalid).",
        )

    day = (await session.execute(select(cfg.day_model).where(cfg.day_model.id == question.day_id))).scalars().first()
    if not day:
        raise HTTPException(status_code=404, detail="Associated day record not found.")

    target_fk = getattr(day, cfg.target_fk_col.key)
    target = (await session.execute(select(cfg.target_model).where(cfg.target_model.id == target_fk))).scalars().first()
    target_name = getattr(target, cfg.target_name_col.key, "Unknown")

    from db.repositories import fallback_answers

    await fallback_answers.invalidate(
        session,
        mode=cfg.mode_key,
        entity_name=target_name,
        original_question=question.original_question,
        question=getattr(question, "question", None),
        context=question.context,
        game_date=day.date,
    )
    await session.commit()
    return True, f"Fallback answer for '{target_name}' invalidated and signature blocked."
