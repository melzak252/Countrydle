import asyncio
import hashlib
import json
import math
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, StrictInt, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models.heraldry_quiz import QuizRun, QuizSolve
from powiatdle.utils import LOCAL_CONFIG
from users.utils import get_current_or_guest_user
from utils.guest_session import get_guest_identity, read_guest_identity

SYMBOL_MODE = 'plates'
ENTITY_SCOPE = 'county'

router = APIRouter(prefix='/plates/quiz', tags=['plates-quiz'])


def get_db_path() -> Path:
    return LOCAL_CONFIG.db_path


def normalize_plate(text: str) -> str:
    return re.sub(r'[^A-Z]', '', text.strip().upper())


def finite_input(value):
    # Keep rejected NaN/Infinity out of FastAPI's JSON validation response.
    return 'nonfinite' if isinstance(value, float) and not math.isfinite(value) else value


class StartRequest(BaseModel):
    pass


class SolveRequest(BaseModel):
    powiat_ids: list[StrictInt] = Field(min_length=1, max_length=380)
    answer: str = Field(min_length=1, max_length=32)
    elapsed_seconds: float = Field(ge=0, allow_inf_nan=False)

    _finite_elapsed = field_validator('elapsed_seconds', mode='before')(finite_input)


class FinishRequest(BaseModel):
    status: Literal['completed', 'given_up']
    elapsed_seconds: float = Field(ge=0, allow_inf_nan=False)
    solves: list[SolveRequest] = Field(max_length=380)

    _finite_elapsed = field_validator('elapsed_seconds', mode='before')(finite_input)


def _read_plates_catalog_sync(db_path: Path) -> dict[int, set[str]]:
    if not db_path.exists():
        raise FileNotFoundError(f'Missing powiat facts database: {db_path}')
    with sqlite3.connect(db_path) as conn:
        powiat_rows = conn.execute('SELECT id FROM powiats').fetchall()
        plate_rows = conn.execute(
            'SELECT powiat_id, plate_code FROM powiat_registration_plates'
        ).fetchall()
    catalog: dict[int, set[str]] = {int(row[0]): set() for row in powiat_rows}
    for powiat_id, plate_code in plate_rows:
        pid = int(powiat_id)
        code = normalize_plate(str(plate_code or ''))
        if pid in catalog and code:
            catalog[pid].add(code)
    return {pid: codes for pid, codes in catalog.items() if codes}


async def load_plates_catalog() -> dict[int, set[str]]:
    db_path = get_db_path()
    try:
        catalog = await asyncio.to_thread(_read_plates_catalog_sync, db_path)
    except (OSError, sqlite3.Error) as exc:
        raise HTTPException(status_code=503, detail='Plates quiz catalog is unavailable') from exc
    if not catalog:
        raise HTTPException(status_code=503, detail='Plates quiz catalog is unavailable')
    return catalog


def validated_plates_solves(
    body: FinishRequest,
    catalog: dict[int, set[str]],
) -> list[tuple[int, float]]:
    max_entities = len(catalog)
    if (
        not math.isfinite(body.elapsed_seconds)
        or body.elapsed_seconds < 0
        or len(body.solves) > max_entities
    ):
        raise HTTPException(status_code=422, detail='Invalid quiz duration or solve count')

    seen: set[int] = set()
    flattened: list[tuple[int, float]] = []
    previous = 0.0
    for event in body.solves:
        if (
            not event.powiat_ids
            or not math.isfinite(event.elapsed_seconds)
            or event.elapsed_seconds < previous
            or event.elapsed_seconds > body.elapsed_seconds
        ):
            raise HTTPException(status_code=422, detail='Invalid solve time or IDs')

        code = normalize_plate(event.answer)
        if not code:
            raise HTTPException(status_code=422, detail='Invalid plate code')

        for id_ in event.powiat_ids:
            if id_ in seen or id_ not in catalog or code not in catalog[id_]:
                raise HTTPException(status_code=422, detail='Invalid or repeated plate answer')
            seen.add(id_)
            if len(seen) > max_entities:
                raise HTTPException(status_code=422, detail='Too many solved counties')
            flattened.append((id_, event.elapsed_seconds))
        previous = event.elapsed_seconds

    if body.status == 'completed' and seen != set(catalog.keys()):
        raise HTTPException(status_code=422, detail='Completed runs must solve the entire catalog')
    return flattened


def fingerprint(body: FinishRequest) -> str:
    data = body.model_dump()
    encoded = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()


@router.post('/runs')
async def start_run(
    body: StartRequest,
    request: Request,
    response: Response,
    user=Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    await load_plates_catalog()
    run = QuizRun(
        user_id=user.id if user else None,
        guest_id=None if user else get_guest_identity(request, response),
        status='started',
        solved_count=0,
        symbol_mode=SYMBOL_MODE,
        entity_scope=ENTITY_SCOPE,
    )
    session.add(run)
    await session.commit()
    return {'run_id': run.id}


@router.post('/runs/{run_id}/finish')
async def finish_run(
    run_id: str,
    body: FinishRequest,
    request: Request,
    user=Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    guest = read_guest_identity(request)
    if not user and guest is None:
        raise HTTPException(status_code=404, detail='Run not found')
    owner = QuizRun.user_id == user.id if user else QuizRun.guest_id == guest
    if user and guest:
        owner = or_(owner, (QuizRun.user_id.is_(None)) & (QuizRun.guest_id == guest))

    run = await session.scalar(
        select(QuizRun)
        .where(
            QuizRun.id == run_id,
            QuizRun.symbol_mode == SYMBOL_MODE,
            QuizRun.entity_scope == ENTITY_SCOPE,
            owner,
        )
        .with_for_update()
    )
    if run is None:
        raise HTTPException(status_code=404, detail='Run not found')

    try:
        result_hash = fingerprint(body)
    except ValueError:
        raise HTTPException(status_code=422, detail='Invalid quiz duration or solve time')

    if run.status != 'started':
        if run.result_hash != result_hash:
            raise HTTPException(status_code=409, detail='Run already finished with a different result')
        if user and run.user_id is None:
            run.user_id, run.guest_id = user.id, None
            await session.commit()
        return {'run_id': run.id, 'status': run.status, 'solved_count': run.solved_count}

    catalog = await load_plates_catalog()
    solves = validated_plates_solves(body, catalog)
    if user and run.user_id is None:
        run.user_id, run.guest_id = user.id, None
    session.add_all(
        [QuizSolve(run_id=run.id, powiat_id=id_, elapsed_seconds=seconds) for id_, seconds in solves]
    )
    run.status = body.status
    run.elapsed_seconds = body.elapsed_seconds
    run.solved_count = len(solves)
    run.finished_at = datetime.now(timezone.utc)
    run.result_hash = result_hash
    await session.commit()
    return {'run_id': run.id, 'status': run.status, 'solved_count': run.solved_count}


@router.get('/stats')
async def stats(session: AsyncSession = Depends(get_db)):
    catalog = await load_plates_catalog()
    finished = QuizRun.status.in_(('completed', 'given_up'))
    finished_runs, tracking_started_at = (
        await session.execute(
            select(func.count(QuizRun.id).filter(finished), func.min(QuizRun.started_at)).where(
                QuizRun.symbol_mode == SYMBOL_MODE,
                QuizRun.entity_scope == ENTITY_SCOPE,
            )
        )
    ).one()
    rows = (
        await session.execute(
            select(QuizSolve.powiat_id, func.count(QuizSolve.run_id), func.avg(QuizSolve.elapsed_seconds))
            .join(QuizRun, QuizRun.id == QuizSolve.run_id)
            .where(
                finished,
                QuizRun.symbol_mode == SYMBOL_MODE,
                QuizRun.entity_scope == ENTITY_SCOPE,
            )
            .group_by(QuizSolve.powiat_id)
            .order_by(QuizSolve.powiat_id)
        )
    ).all()
    aggregates = {id_: (count, average) for id_, count, average in rows}
    return {
        'finished_runs': finished_runs,
        'tracking_started_at': tracking_started_at,
        'powiats': [
            {
                'powiat_id': id_,
                'solved_count': aggregates.get(id_, (0, None))[0],
                'average_active_seconds': aggregates.get(id_, (0, None))[1],
            }
            for id_ in sorted(catalog)
        ],
    }
