"""Persistent, report-invalidatable cache for strict fallback answers."""
from dataclasses import dataclass
from datetime import date
import hashlib
import json

from sqlalchemy import delete, exists, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from db.models.fallback_answer import FallbackAnswer, FallbackAnswerBlock

STRICT_ANSWER_SCHEMA_VERSION = "strict-answer-v1"


@dataclass(frozen=True)
class CacheIdentity:
    key: str
    signature: str
    game_date: date


def _canonical_mode(mode: str) -> str:
    return "countrydle" if mode == "continental" else mode


def _json_digest(payload: dict) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _date_text(game_date: date) -> str:
    return game_date.isoformat()


def make_signature(
    *,
    mode: str,
    entity_name: str,
    original_question: str,
    question: str | None,
    context: str,
    game_date: date,
) -> str:
    """Hash exact question/context identity while retaining no source text."""
    context_hash = hashlib.sha256(context.encode("utf-8")).hexdigest()
    return _json_digest({
        "mode": _canonical_mode(mode),
        "entity_name": entity_name,
        "original_question": original_question,
        "question": question,
        "context_hash": context_hash,
        "game_date": _date_text(game_date),
    })


def make_identity(
    *,
    mode: str,
    entity_id: int,
    entity_name: str,
    original_question: str,
    question: str | None,
    context: str,
    system_prompt: str,
    question_prompt: str,
    model: str,
    game_date: date,
) -> CacheIdentity:
    canonical_mode = _canonical_mode(mode)
    signature = make_signature(
        mode=canonical_mode,
        entity_name=entity_name,
        original_question=original_question,
        question=question,
        context=context,
        game_date=game_date,
    )
    key = _json_digest({
        "signature": signature,
        "mode": canonical_mode,
        "entity_id": entity_id,
        "model": model,
        "system_prompt": system_prompt,
        "question_prompt": question_prompt,
        "strict_answer_schema_version": STRICT_ANSWER_SCHEMA_VERSION,
    })
    return CacheIdentity(key=key, signature=signature, game_date=game_date)


def _insert_for_session(session: AsyncSession, model):
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        return postgresql_insert(model)
    if dialect == "sqlite":
        return sqlite_insert(model)
    raise NotImplementedError(f"Fallback answer cache does not support {dialect!r}")


async def lookup(session: AsyncSession, identity: CacheIdentity) -> dict | None:
    """Return a cached strict answer only while its signature is not blocked."""
    is_blocked = exists(
        select(1).select_from(FallbackAnswerBlock).where(
            FallbackAnswerBlock.signature == identity.signature
        )
    )
    result = await session.execute(
        select(FallbackAnswer.answer, FallbackAnswer.explanation).where(
            FallbackAnswer.key == identity.key,
            FallbackAnswer.signature == identity.signature,
            FallbackAnswer.game_date == identity.game_date,
            ~is_blocked,
        )
    )
    row = result.one_or_none()
    if row is None:
        return None
    return {"answer": row.answer, "explanation": row.explanation}


async def store(
    session: AsyncSession,
    identity: CacheIdentity,
    answer: bool,
    explanation: str,
) -> None:
    """Insert once, atomically refusing signatures already invalidated by a report."""
    if type(answer) is not bool:
        raise ValueError("Fallback answer cache accepts only strict boolean answers")
    if not isinstance(explanation, str):
        raise ValueError("Fallback answer explanation must be text")

    unblocked_values = select(
        literal(identity.key),
        literal(identity.signature),
        literal(identity.game_date),
        literal(answer),
        literal(explanation),
    ).where(
        ~exists(
            select(1).select_from(FallbackAnswerBlock).where(
                FallbackAnswerBlock.signature == identity.signature
            )
        )
    )
    statement = _insert_for_session(session, FallbackAnswer).from_select(
        ["key", "signature", "game_date", "answer", "explanation"],
        unblocked_values,
    ).on_conflict_do_nothing(index_elements=[FallbackAnswer.key])
    await session.execute(statement)


def _coerce_game_date(game_date: date | str) -> date:
    if isinstance(game_date, str):
        return date.fromisoformat(game_date)
    if isinstance(game_date, date):
        return game_date
    raise TypeError("game_date must be a date or ISO date string")


async def invalidate(
    session: AsyncSession,
    *,
    mode: str,
    entity_name: str,
    original_question: str,
    question: str | None,
    context: str | None,
    game_date: date | str,
) -> None:
    """Block a daily question signature and remove its existing entries atomically."""
    if not context:
        return
    normalized_date = _coerce_game_date(game_date)
    signature = make_signature(
        mode=mode,
        entity_name=entity_name,
        original_question=original_question,
        question=question,
        context=context,
        game_date=normalized_date,
    )
    block = _insert_for_session(session, FallbackAnswerBlock).values(
        signature=signature,
        game_date=normalized_date,
    ).on_conflict_do_nothing(index_elements=[FallbackAnswerBlock.signature])
    await session.execute(block)
    await session.execute(
        delete(FallbackAnswer).where(FallbackAnswer.signature == signature)
    )


async def purge_old(session: AsyncSession, before: date) -> None:
    """Delete cache entries and report blocks for dates strictly before ``before``."""
    await session.execute(delete(FallbackAnswer).where(FallbackAnswer.game_date < before))
    await session.execute(delete(FallbackAnswerBlock).where(FallbackAnswerBlock.game_date < before))
