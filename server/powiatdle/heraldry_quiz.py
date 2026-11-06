import asyncio
import hashlib
import json
import math
import sqlite3
import re
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, StrictInt, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models.heraldry_quiz import QuizRun, QuizSolve
from users.utils import get_current_or_guest_user
from utils.guest_session import get_guest_identity, read_guest_identity

router = APIRouter(prefix='/quiz', tags=['heraldry-quiz'])
flags_quiz_router = APIRouter(prefix='/quiz', tags=['flags-quiz'])


def symbol_mode(request: Request) -> str:
    return 'flag' if '/flags/quiz/' in request.url.path else 'coat'


_TRANSLATION = str.maketrans('ąćęłńóśźż', 'acelnoszz')


def normalize(text: str) -> str:
    text = text.lower().translate(_TRANSLATION)
    return re.sub(r'\s+', ' ', re.sub(r'[-–—./]', ' ', text)).strip()


def accepted_forms(name: str) -> set[str]:
    forms = set()
    for candidate in (name, re.sub(r'\s*\([^)]*\)', '', name).strip()):
        full = normalize(candidate)
        if not full:
            continue
        forms.add(full)
        if full.startswith('powiat '):
            short = full[len('powiat '):].strip()
            if short:
                forms.update((short, 'pow ' + short))
        else:
            forms.update(('m ' + full, 'miasto ' + full))
    return forms



def finite_input(value):
    # Keep rejected NaN/Infinity out of FastAPI's JSON validation response.
    return 'nonfinite' if isinstance(value, float) and not math.isfinite(value) else value



class StartRequest(BaseModel):
    pass


class SolveRequest(BaseModel):
    powiat_ids: list[StrictInt] = Field(min_length=1, max_length=380)
    answer: str = Field(min_length=1, max_length=200)
    elapsed_seconds: float = Field(ge=0, allow_inf_nan=False)

    _finite_elapsed = field_validator('elapsed_seconds', mode='before')(finite_input)


class FinishRequest(BaseModel):
    status: Literal['completed', 'given_up']
    elapsed_seconds: float = Field(ge=0, allow_inf_nan=False)
    solves: list[SolveRequest] = Field(max_length=380)

    _finite_elapsed = field_validator('elapsed_seconds', mode='before')(finite_input)


def validated_solves(body: FinishRequest, catalog: dict[int, str]) -> list[tuple[int, float]]:
    if not math.isfinite(body.elapsed_seconds) or body.elapsed_seconds < 0 or len(body.solves) > 380:
        raise HTTPException(status_code=422, detail='Invalid quiz duration or solve count')
    forms = {id_: accepted_forms(name) for id_, name in catalog.items()}
    seen = set()
    flattened = []
    previous = 0.0
    for event in body.solves:
        if (not event.powiat_ids or not math.isfinite(event.elapsed_seconds)
                or event.elapsed_seconds < previous or event.elapsed_seconds > body.elapsed_seconds):
            raise HTTPException(status_code=422, detail='Invalid solve time or IDs')
        answer = normalize(event.answer)
        for id_ in event.powiat_ids:
            if id_ in seen or id_ not in forms or answer not in forms[id_]:
                raise HTTPException(status_code=422, detail='Invalid or repeated quiz answer')
            seen.add(id_)
            if len(seen) > 380:
                raise HTTPException(status_code=422, detail='Too many solved counties')
            flattened.append((id_, event.elapsed_seconds))
        previous = event.elapsed_seconds
    if body.status == 'completed' and seen != catalog.keys():
        raise HTTPException(status_code=422, detail='Completed runs must solve the entire catalog')
    return flattened


def fingerprint(body: FinishRequest) -> str:
    # Canonicalize JSON numbers through the request schema, but retain event order,
    # answers and grouping so a replay cannot silently rewrite a finished result.
    data = body.model_dump()
    encoded = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()

async def load_catalog() -> dict[int, str]:
    # Import lazily because the heraldry router includes this router.
    from powiatdle.heraldry import get_all_counties

    try:
        counties = await asyncio.to_thread(get_all_counties)
    except (OSError, sqlite3.Error) as exc:
        raise HTTPException(status_code=503, detail='Quiz catalog is unavailable') from exc
    catalog = {county['id']: county['name'] for county in counties}
    if len(catalog) != 380:
        raise HTTPException(status_code=503, detail='Quiz catalog is unavailable')
    return catalog


async def load_mode_catalog(mode: str) -> dict[int, str]:
    catalog = await load_catalog()
    if mode == 'coat':
        return catalog
    from powiatdle.flag_catalog import load_catalog as load_flags

    flags = load_flags()
    eligible = {id_: catalog[id_] for id_ in flags if id_ in catalog}
    if not eligible:
        raise HTTPException(status_code=503, detail='Flag quiz catalog is unavailable')
    return eligible



@router.post('/runs')
@flags_quiz_router.post('/runs')
async def start_run(body: StartRequest, request: Request, response: Response,
                    user=Depends(get_current_or_guest_user), session: AsyncSession = Depends(get_db)):
    mode = symbol_mode(request)
    if mode == 'flag':
        await load_mode_catalog(mode)
    run = QuizRun(user_id=user.id if user else None,
                  guest_id=None if user else get_guest_identity(request, response), status='started', solved_count=0,
                  symbol_mode=mode)
    session.add(run)
    await session.commit()
    return {'run_id': run.id}


@router.post('/runs/{run_id}/finish')
@flags_quiz_router.post('/runs/{run_id}/finish')
async def finish_run(run_id: str, body: FinishRequest, request: Request,
                     user=Depends(get_current_or_guest_user), session: AsyncSession = Depends(get_db)):
    guest = read_guest_identity(request)
    if not user and guest is None:
        raise HTTPException(status_code=404, detail='Run not found')
    owner = QuizRun.user_id == user.id if user else QuizRun.guest_id == guest
    if user and guest:
        owner = or_(owner, (QuizRun.user_id.is_(None)) & (QuizRun.guest_id == guest))
    mode = symbol_mode(request)
    run = await session.scalar(select(QuizRun).where(
        QuizRun.id == run_id, QuizRun.symbol_mode == mode, owner).with_for_update())
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
    solves = validated_solves(body, await load_mode_catalog(mode))
    if user and run.user_id is None:
        run.user_id, run.guest_id = user.id, None
    session.add_all([QuizSolve(run_id=run.id, powiat_id=id_, elapsed_seconds=seconds) for id_, seconds in solves])
    run.status = body.status
    run.elapsed_seconds = body.elapsed_seconds
    run.solved_count = len(solves)
    run.finished_at = datetime.now(timezone.utc)
    run.result_hash = result_hash
    await session.commit()
    return {'run_id': run.id, 'status': run.status, 'solved_count': run.solved_count}


@router.get('/stats')
@flags_quiz_router.get('/stats')
async def stats(request: Request, session: AsyncSession = Depends(get_db)):
    mode = symbol_mode(request)
    catalog = await load_mode_catalog(mode)
    finished = QuizRun.status.in_(('completed', 'given_up'))
    finished_runs, tracking_started_at = (await session.execute(
        select(func.count(QuizRun.id).filter(finished), func.min(QuizRun.started_at))
        .where(QuizRun.symbol_mode == mode)
    )).one()
    rows = (await session.execute(
        select(QuizSolve.powiat_id, func.count(QuizSolve.run_id), func.avg(QuizSolve.elapsed_seconds))
        .join(QuizRun, QuizRun.id == QuizSolve.run_id).where(finished, QuizRun.symbol_mode == mode)
        .group_by(QuizSolve.powiat_id).order_by(QuizSolve.powiat_id)
    )).all()
    aggregates = {id_: (count, average) for id_, count, average in rows}
    return {'finished_runs': finished_runs, 'tracking_started_at': tracking_started_at,
            ('flags' if mode == 'flag' else 'coats'): [{'powiat_id': id_, 'solved_count': aggregates.get(id_, (0, None))[0],
                       'average_active_seconds': aggregates.get(id_, (0, None))[1]}
                      for id_ in sorted(catalog)]}
