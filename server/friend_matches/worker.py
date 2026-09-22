"""Database-claimed advisory work and independent authoritative deadline sweep."""
import asyncio
import logging
import os
import re
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import and_, delete, func, or_, select

from db import AsyncSessionLocal
from db.models.friend_match import FriendAdvisory, FriendMatch, FriendMove, FriendReport, FriendSeat
from .providers import evaluate_question
from .service import expire_locked, iso, locked_match, utcnow

logger = logging.getLogger(__name__)
LEASE_SECONDS = 90
_tasks = []
_stop = None


def safe_error(exc):
    message = f"{type(exc).__name__}: {exc}"
    for name, value in os.environ.items():
        if len(value) >= 8 and any(word in name.upper() for word in ("KEY", "TOKEN", "SECRET", "PASSWORD", "DATABASE_URL")):
            message = message.replace(value, "[redacted]")
    return re.sub(r"(?i)(api[_-]?key|access[_-]?token|authorization)([=:]\s*)[^\s&]+",
                  r"\1\2[redacted]", message)[:4000]


async def claim_job():
    now = utcnow()
    async with AsyncSessionLocal() as session, session.begin():
        job = await session.scalar(select(FriendAdvisory).where(or_(
            FriendAdvisory.status == "pending",
            and_(FriendAdvisory.status == "running", FriendAdvisory.lease_until < now),
        )).order_by(FriendAdvisory.created_at).limit(1).with_for_update(skip_locked=True))
        if not job:
            return None
        if job.status == "running":
            job.attempts = [*job.attempts, {"status": "interrupted", "lease_token": job.lease_token,
                                          "started_at": iso(job.started_at), "recorded_at": iso(now),
                                          "error": "Worker lease expired; no output was recorded."}]
        move = await session.get(FriendMove, job.question_id)
        match = await session.get(FriendMatch, job.match_id)
        job.status, job.started_at, job.lease_token = "running", now, str(uuid4())
        job.lease_until = now + timedelta(seconds=LEASE_SECONDS)
        return {"question_id": job.question_id, "match_id": job.match_id, "lease_token": job.lease_token,
                "mode": match.mode, "entity": move.target, "question": move.question, "started_at": iso(now)}


async def renew_lease(claim, finished):
    while not finished.is_set():
        try:
            await asyncio.wait_for(finished.wait(), timeout=LEASE_SECONDS / 3)
            return
        except asyncio.TimeoutError:
            pass
        try:
            async with AsyncSessionLocal() as session, session.begin():
                job = await session.scalar(select(FriendAdvisory).where(
                    FriendAdvisory.question_id == claim["question_id"]).with_for_update())
                if job.lease_token != claim["lease_token"] or job.status != "running":
                    return
                job.lease_until = utcnow() + timedelta(seconds=LEASE_SECONDS)
        except Exception:
            logger.exception("Could not renew friend advisory lease %s", claim["question_id"])


def record_completion(job, claim, result, error, now, *, late):
    """Preserve even output returned after another worker reclaimed an expired lease."""
    current = job.lease_token == claim["lease_token"] and job.status == "running"
    attempt = {"status": "failed" if error else "completed", "lease_token": claim["lease_token"],
               "started_at": claim["started_at"], "completed_at": iso(now), "late": late,
               "superseded": not current, "result": result, "error": error}
    job.attempts = [*job.attempts, attempt]
    if not current:
        return
    job.status = "failed" if error else "completed"
    job.completed_at, job.late, job.error = now, late, error
    job.lease_until = None
    if result:
        job.answer, job.explanation, job.source = result["answer"], result["explanation"], result["source"]
        job.interpretation, job.evidence = result.get("interpretation"), result.get("evidence", {})
    elif error:
        job.evidence = {"error": error, "kind": "provider_failure"}


async def store_completion(claim, result=None, error=None):
    now = utcnow()
    async with AsyncSessionLocal() as session, session.begin():
        # The lock orders completion with human answers but does not change gameplay version.
        match, _ = await locked_match(session, claim["match_id"])
        job = await session.scalar(select(FriendAdvisory).where(
            FriendAdvisory.question_id == claim["question_id"]).with_for_update())
        move = await session.get(FriendMove, claim["question_id"])
        record_completion(job, claim, result, error, now,
                          late=bool(move.answer or move.timed_out or match.status == "finished"))


async def run_job(claim):
    finished = asyncio.Event()
    renewal = asyncio.create_task(renew_lease(claim, finished))
    result = error = None
    try:
        # claim_job already committed and returned its connection to the pool.
        result = await evaluate_question(claim["mode"], claim["entity"], claim["question"])
        if (result.get("answer") not in {"YES", "NO", "INVALID"}
                or not isinstance(result.get("explanation"), str)
                or not isinstance(result.get("source"), str) or not result["source"].strip()):
            raise ValueError("Provider returned an invalid advisory result")
    except asyncio.CancelledError:
        # The lease will recover after hard shutdown; never invent an AI answer.
        raise
    except Exception as exc:
        result = None
        error = safe_error(exc)
    finally:
        finished.set()
        await renewal
    # Retry persistence, not the model request: completed output must not be lost on a DB hiccup.
    while True:
        try:
            await store_completion(claim, result, error)
            return
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Could not persist friend advisory %s", claim["question_id"])
            await asyncio.sleep(2)


async def pause(stop, seconds):
    try:
        await asyncio.wait_for(stop.wait(), seconds)
    except asyncio.TimeoutError:
        pass


async def advisory_loop(stop):
    while not stop.is_set():
        try:
            claim = await claim_job()
            if claim:
                await run_job(claim)
                continue
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Friend advisory worker failed to claim work")
        await pause(stop, 1)


async def sweep_deadlines():
    now = utcnow()
    async with AsyncSessionLocal() as session, session.begin():
        # Bounded batches allow multiple application processes to share the sweep.
        lobby_present = select(FriendSeat.id).where(
            FriendSeat.match_id == FriendMatch.id,
            FriendSeat.last_seen_at >= now - timedelta(minutes=30),
        ).exists()
        matches = (await session.scalars(select(FriendMatch).where(or_(
            FriendMatch.status == "active",
            and_(FriendMatch.status == "lobby", ~lobby_present),
        )).order_by(func.coalesce(FriendMatch.deadline, FriendMatch.created_at)).limit(1000)
            .with_for_update(skip_locked=True))).all()
        if not matches:
            return
        seats_by_match = {}
        for seat in (await session.scalars(select(FriendSeat).where(
            FriendSeat.match_id.in_([match.id for match in matches])).order_by(FriendSeat.position))).all():
            seats_by_match.setdefault(seat.match_id, []).append(seat)
        for match in matches:
            await expire_locked(session, match, seats_by_match.get(match.id, []), now)


async def deadline_loop(stop):
    while not stop.is_set():
        try:
            await sweep_deadlines()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Friend match deadline sweep failed")
        await pause(stop, 1)


async def prune_evidence():
    now = utcnow()
    async with AsyncSessionLocal() as session, session.begin():
        busy = select(FriendAdvisory.question_id).where(
            FriendAdvisory.match_id == FriendMatch.id,
            FriendAdvisory.status.in_(["pending", "running"]),
        ).exists()
        last_review = select(func.max(FriendMove.reviewed_at)).where(
            FriendMove.match_id == FriendMatch.id).correlate(FriendMatch).scalar_subquery()
        last_report = select(func.max(FriendReport.created_at)).join(
            FriendMove, FriendMove.id == FriendReport.question_id).where(
                FriendMove.match_id == FriendMatch.id).correlate(FriendMatch).scalar_subquery()
        unreviewed_report = select(FriendReport.id).join(
            FriendMove, FriendMove.id == FriendReport.question_id).where(
                FriendMove.match_id == FriendMatch.id,
                or_(FriendMove.reviewed_at.is_(None), FriendMove.review_status == "new",
                    FriendMove.reviewed_at < FriendReport.created_at),
            ).exists()
        ordinary = and_(last_review.is_(None), last_report.is_(None),
                        FriendMatch.finished_at < now - timedelta(days=30))
        reviewed = and_(or_(last_review.is_not(None), last_report.is_not(None)),
                        func.greatest(FriendMatch.finished_at, last_review, last_report) < now - timedelta(days=90))
        matches = (await session.scalars(select(FriendMatch).where(
            FriendMatch.status == "finished", ~busy, ~unreviewed_report, or_(ordinary, reviewed),
        ).order_by(FriendMatch.finished_at).limit(100).with_for_update(skip_locked=True))).all()
        for match in matches:
            await session.execute(delete(FriendMatch).where(FriendMatch.id == match.id))


async def retention_loop(stop):
    while not stop.is_set():
        try:
            await prune_evidence()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Friend duel evidence retention failed")
        await pause(stop, 3600)


async def start_workers():
    global _stop, _tasks
    if _tasks:
        return
    _stop = asyncio.Event()
    concurrency = max(1, min(16, int(os.getenv("FRIEND_AI_WORKERS", "2"))))
    _tasks = [asyncio.create_task(deadline_loop(_stop), name="friend-deadlines"),
              asyncio.create_task(retention_loop(_stop), name="friend-retention")]
    _tasks.extend(asyncio.create_task(advisory_loop(_stop), name=f"friend-advisory-{i}") for i in range(concurrency))


async def stop_workers():
    global _stop, _tasks
    if not _tasks:
        return
    _stop.set()
    # Graceful shutdown keeps awaiting real results, including after the match ends.
    # A killed process is recovered using its expired PostgreSQL lease on restart.
    await asyncio.gather(*_tasks, return_exceptions=True)
    _tasks = []
    _stop = None
