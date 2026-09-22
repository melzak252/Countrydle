"""Human gameplay is transactional; advisory output never participates in a turn."""
import asyncio
import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import and_, case, func, or_, select

from db import AsyncSessionLocal
from db.models.friend_match import FriendAction, FriendAdvisory, FriendMatch, FriendMove, FriendReport, FriendSeat
from .providers import list_entities
from .schemas import ActionRequest

THINK_SECONDS = 120
ANSWER_SECONDS = 60
DISCONNECT_SECONDS = 30
CONNECTED_SECONDS = 15
INFRASTRUCTURE_GRACE_SECONDS = 10
HISTORY_PAGE_SIZE = 50


def utcnow():
    return datetime.now(timezone.utc)


def iso(value):
    return value.isoformat() if value else None


def fail(message, status=409):
    raise HTTPException(status_code=status, detail=message)


def credential_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def require_admission():
    if os.getenv("FRIEND_MATCHES_ENABLED", "true").lower() not in {"true", "1", "yes"}:
        fail("New friend matches are temporarily unavailable. Existing matches can continue.", 503)


def action_hash(action):
    payload = {"type": action.type, "payload": action.payload, "expected_version": action.expected_version}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def finish(match, result, now, winner=None):
    match.status, match.phase, match.result = "finished", "finished", result
    match.winner_id, match.finished_at = winner, now
    match.active_player_id = match.pending_question_id = match.deadline = None
    match.draw_offer_by = None


def advance(match, next_player, now):
    match.active_player_id = next_player.id
    match.phase = "thinking"
    match.pending_question_id = None
    match.turn += 1
    match.deadline = now + timedelta(seconds=THINK_SECONDS)


def start_if_ready(match, seats, now):
    if match.status == "lobby" and len(seats) == 2 and all(
        s.ready and s.secret and (now - s.last_seen_at).total_seconds() < CONNECTED_SECONDS for s in seats
    ):
        match.status = "active"
        advance(match, seats[0], now)
        return True
    return False


def expire_match(match, seats, now, *, pending_move=None, advisory=None, timeout_moves=None):
    if match.status == "lobby":
        if seats and all(now - s.last_seen_at >= timedelta(minutes=30) for s in seats):
            finish(match, "cancelled", now)
            match.version += 1
            return True
        return False
    if match.status != "active":
        return False
    opponent = {s.id: next(other for other in seats if other.id != s.id) for s in seats}
    if match.deadline and now >= match.deadline:
        if (now - match.deadline).total_seconds() > INFRASTRUCTURE_GRACE_SECONDS:
            finish(match, "interrupted", now)
        elif match.phase == "reply":
            finish(match, "solved", now, match.pending_winner_id)
        else:
            actor = (opponent[match.active_player_id] if match.phase == "answering"
                     else next(s for s in seats if s.id == match.active_player_id))
            actor.timeout_count += 1
            if pending_move is not None:
                pending_move.timed_out = True
                # If player didn't answer in time, automatically provide AI answer
                ai_answer = "unknown"
                if advisory and advisory.status == "completed":
                    if advisory.answer == "YES":
                        ai_answer = "yes"
                    elif advisory.answer == "NO":
                        ai_answer = "no"
                pending_move.answer = ai_answer
                pending_move.answered_at = now
                match.pending_question_id = None
            elif match.phase == "thinking":
                match.move_ordinal += 1
                timeout_move = FriendMove(
                    id=str(uuid4()), match_id=match.id, ordinal=match.move_ordinal, type="pass",
                    player_id=actor.id, subject_id=opponent[actor.id].id, timed_out=True,
                    revision=1, revisions=[], created_at=now, ai_seen_before_answer=False,
                    review_status="new", review_note="", review_history=[],
                )
                if timeout_moves is not None:
                    timeout_moves.append(timeout_move)
            if actor.timeout_count >= 2:
                finish(match, "forfeit", now, opponent[actor.id].id)
            else:
                advance(match, actor if match.phase == "answering" else opponent[actor.id], now)
        match.version += 1
        return True
    disconnected = [s for s in seats if (now - s.last_seen_at).total_seconds() >= DISCONNECT_SECONDS]
    if disconnected:
        late = all((now - s.last_seen_at).total_seconds() > DISCONNECT_SECONDS + INFRASTRUCTURE_GRACE_SECONDS for s in disconnected)
        interrupted = len(disconnected) == 2 or late
        finish(match, "interrupted" if interrupted else "forfeit", now,
               None if interrupted else opponent[disconnected[0].id].id)
        match.version += 1
        return True
    return False


async def expire_locked(session, match, seats, now):
    pending = None
    advisory = None
    if match.pending_question_id and match.deadline and now >= match.deadline:
        pending = await session.get(FriendMove, match.pending_question_id)
        if pending:
            advisory = await session.get(FriendAdvisory, pending.id)
    moves = []
    changed = expire_match(match, seats, now, pending_move=pending, advisory=advisory, timeout_moves=moves)
    session.add_all(moves)
    return changed


def transition(match, seats, actor, action, now, *, entity=None, move=None, advisory=None):
    """Apply one validated action with the match row locked. No I/O or model calls."""
    kind, payload = action.type, action.payload
    other = next((s for s in seats if s.id != actor.id), None)
    if kind in {"select_secret", "randomize_secret", "ready"}:
        if match.status != "lobby":
            fail("Secrets and readiness can only change in the lobby.")
        if kind == "ready":
            if payload["ready"] and not actor.secret:
                fail("Choose your secret first.")
            actor.ready = payload["ready"]
        else:
            if actor.ready:
                fail("Unready before changing your secret.")
            actor.secret = entity
        start_if_ready(match, seats, now)
        return None
    if kind == "rematch":
        if match.status != "finished" or len(seats) != 2:
            fail("Both players can request a rematch after the game ends.")
        actor.rematch_ready = True
        return None
    if kind == "correct_answer":
        if match.status != "active":
            fail("Answers can only be corrected during play. Submit a report after the match.")
        if not move or move.type != "question" or move.match_id != match.id:
            fail("Question not found.", 404)
        if move.subject_id != actor.id:
            fail("Only the secret owner can correct this answer.", 403)
        if not move.answer or move.revision != payload["expected_revision"]:
            fail("The answer changed. Refresh before correcting it.")
        move.revision += 1
        move.answer, move.answered_at = payload["answer"], now
        move.ai_seen_before_answer = bool(advisory and advisory.status == "completed" and
            payload.get("observed_ai_question_id") == move.id and advisory.completed_at and advisory.completed_at <= now)
        move.revisions = [*move.revisions, {"answer": move.answer, "revision": move.revision,
                         "created_at": iso(now), "ai_seen_before_answer": move.ai_seen_before_answer}]
        return None
    if match.status == "finished":
        fail("This match has already finished.")
    if kind == "leave":
        finish(match, "forfeit" if match.status == "active" else "cancelled", now,
               other.id if other and match.status == "active" else None)
        return None
    if match.status != "active":
        fail("Both players must choose a secret and be ready.")
    if kind == "offer_draw":
        if match.draw_offer_by:
            fail("There is already a draw offer.")
        match.draw_offer_by = actor.id
        return None
    if kind in {"accept_draw", "decline_draw"}:
        if not match.draw_offer_by or match.draw_offer_by == actor.id:
            fail("Only the opponent can respond to a draw offer.")
        if kind == "accept_draw":
            finish(match, "draw", now)
        else:
            match.draw_offer_by = None
        return None
    if kind == "answer":
        if not move or move.match_id != match.id or move.subject_id != actor.id:
            fail("Only the secret owner can answer this question.", 403)
        if match.phase != "answering" or match.pending_question_id != move.id or move.answer:
            fail("This question is no longer awaiting an answer.")
        actor.timeout_count = 0
        seen = bool(advisory and advisory.status == "completed" and
                    payload.get("observed_ai_question_id") == move.id and
                    advisory.completed_at and advisory.completed_at <= now)
        move.answer, move.answered_at = payload["answer"], now
        move.ai_seen_before_answer = seen
        move.revisions = [{"answer": move.answer, "revision": 1, "created_at": iso(now), "ai_seen_before_answer": seen}]
        advance(match, actor, now)
        return None
    if match.active_player_id != actor.id or match.phase not in {"thinking", "reply"}:
        fail("It is not your turn.")
    if match.phase == "reply" and kind not in {"guess", "pass"}:
        fail("The reply turn allows one guess or a pass.")
    if kind not in {"ask", "guess", "pass"}:
        fail("This action is not available now.")
    actor.timeout_count = 0
    match.move_ordinal += 1
    result = FriendMove(
        id=str(uuid4()), match_id=match.id, ordinal=match.move_ordinal,
        type="question" if kind == "ask" else kind, player_id=actor.id, subject_id=other.id,
        question=payload.get("question"), entity=entity if kind == "guess" else None,
        target=other.secret if kind == "ask" else None, answer=None, correct=None,
        revision=1, revisions=[], created_at=now, ai_seen_before_answer=False, timed_out=False,
        review_status="new", review_note="", review_history=[],
    )
    if kind == "ask":
        actor.question_count += 1
        match.pending_question_id, match.phase = result.id, "answering"
        match.deadline = now + timedelta(seconds=ANSWER_SECONDS)
    elif kind == "guess":
        actor.guess_count += 1
        result.correct = entity["id"] == other.secret["id"]
        if match.phase == "reply":
            finish(match, "draw" if result.correct else "solved", now,
                   None if result.correct else match.pending_winner_id)
        elif result.correct and actor.position == 0:
            match.pending_winner_id = actor.id
            advance(match, other, now)
            match.phase = "reply"
        elif result.correct:
            finish(match, "solved", now, actor.id)
        else:
            advance(match, other, now)
    elif match.phase == "reply":
        finish(match, "solved", now, match.pending_winner_id)
    else:
        advance(match, other, now)
    return result


def project_move(move):
    return {"id": move.id, "ordinal": move.ordinal, "type": move.type,
            "player_id": move.player_id, "subject_id": move.subject_id, "question": move.question,
            "entity": move.entity if move.type == "guess" else None, "answer": move.answer,
            "correct": move.correct, "revision": move.revision, "created_at": iso(move.created_at),
            "timed_out": move.timed_out,
            "answered_by": "ai" if (move.timed_out and move.answer) else ("player" if move.answer else None),
            "revisions": [{"answer": r["answer"], "revision": r["revision"], "created_at": r["created_at"]}
                          for r in move.revisions]}


def project_guidance(job, viewer):
    if job.owner_id != viewer:
        return None
    return {"question_id": job.question_id, "status": job.status, "answer": job.answer,
            "explanation": job.explanation, "source": job.source, "completed_at": iso(job.completed_at),
            "late": job.late}


async def locked_match(session, match_id):
    match = await session.scalar(select(FriendMatch).where(FriendMatch.id == match_id).with_for_update())
    if not match:
        fail("Match not found.", 404)
    seats = list((await session.scalars(select(FriendSeat).where(FriendSeat.match_id == match.id).order_by(FriendSeat.position))).all())
    return match, seats


def authorize(seats, digest):
    actor = next((s for s in seats if secrets.compare_digest(s.credential_hash, digest)), None)
    if not actor:
        fail("This browser does not have a seat in this match.", 403)
    return actor


async def history_page(session, match_id, before=None):
    query = select(FriendMove).where(FriendMove.match_id == match_id)
    if before is not None:
        query = query.where(FriendMove.ordinal < before)
    rows = list((await session.scalars(query.order_by(FriendMove.ordinal.desc()).limit(HISTORY_PAGE_SIZE + 1))).all())
    more = len(rows) > HISTORY_PAGE_SIZE
    rows = rows[:HISTORY_PAGE_SIZE]
    return {"history": [project_move(m) for m in reversed(rows)], "history_has_more": more,
            "next_before": rows[-1].ordinal if more else None}


async def snapshot(session, match, seats, actor, now):
    history = await history_page(session, match.id)
    jobs = (await session.scalars(select(FriendAdvisory).where(
        FriendAdvisory.match_id == match.id, FriendAdvisory.owner_id == actor.id
    ).order_by(FriendAdvisory.created_at.desc()).limit(HISTORY_PAGE_SIZE))).all()
    successor = await session.scalar(select(FriendMatch).where(FriendMatch.parent_id == match.id))
    return {
        "id": match.id, "invite_code": match.invite_code, "mode": match.mode, "version": match.version,
        "status": match.status, "phase": match.phase, "you": actor.id,
        "players": [{"id": s.id, "name": s.name, "ready": s.ready,
                     "connected": (now - s.last_seen_at).total_seconds() < CONNECTED_SECONDS,
                     "guess_count": s.guess_count, "question_count": s.question_count,
                     "rematch_ready": s.rematch_ready, "timeout_count": s.timeout_count} for s in seats],
        "own_secret": actor.secret, "active_player_id": match.active_player_id,
        "pending_question_id": match.pending_question_id, "pending_winner_id": match.pending_winner_id,
        "winner_id": match.winner_id, "result": match.result, "draw_offer_by": match.draw_offer_by,
        "turn": match.turn, "deadline": iso(match.deadline), **history,
        "guidance": [project_guidance(j, actor.id) for j in reversed(jobs)],
        "reveals": [{"player_id": s.id, "entity": s.secret} for s in seats if s.secret] if match.status == "finished" else None,
        "rematch_id": successor.id if successor else None, "rematch_code": successor.invite_code if successor else None,
    }


def make_match(mode, request_id, now, parent_id=None):
    return FriendMatch(id=str(uuid4()), invite_code=secrets.token_urlsafe(18), create_request_id=request_id,
                       parent_id=parent_id, mode=mode, status="lobby", phase="lobby", version=1,
                       turn=0, move_ordinal=0, created_at=now)


def make_seat(match, name, digest, request_id, now, position, user_id=None):
    return FriendSeat(id=str(uuid4()), match_id=match.id, position=position, name=name,
                      credential_hash=digest, join_request_id=request_id, user_id=user_id,
                      ready=False, rematch_ready=False, question_count=0, guess_count=0, timeout_count=0, last_seen_at=now)


async def admit_match(session, digest, now):
    require_admission()
    await session.execute(select(func.pg_advisory_xact_lock(7314962101)))
    active = await session.scalar(select(func.count()).select_from(FriendMatch).where(
        FriendMatch.status.in_(["lobby", "active"])))
    if active >= max(1, int(os.getenv("FRIEND_ACTIVE_ROOM_LIMIT", "500"))):
        fail("Friend rooms are at capacity. Please try again later.", 503)
    recent = await session.scalar(select(func.count()).select_from(FriendSeat).join(
        FriendMatch, FriendMatch.id == FriendSeat.match_id).where(
            FriendSeat.credential_hash == digest, FriendSeat.position == 0,
            FriendMatch.created_at >= now - timedelta(hours=1)))
    if recent >= 8:
        fail("Too many new rooms in a short time. Please wait before creating another.", 429)


async def enqueue_advisory(session, move, now):
    await session.execute(select(func.pg_advisory_xact_lock(7314962102)))
    backlog = await session.scalar(select(func.count()).select_from(FriendAdvisory).where(
        FriendAdvisory.status.in_(["pending", "running"])))
    capacity = backlog >= max(1, int(os.getenv("FRIEND_AI_BACKLOG_LIMIT", "100")))
    session.add(FriendAdvisory(
        question_id=move.id, match_id=move.match_id, owner_id=move.subject_id,
        status="failed" if capacity else "pending", attempts=[], created_at=now, late=False,
        completed_at=now if capacity else None, error="Advisory capacity reached" if capacity else None,
        evidence={"kind": "capacity", "error": "Advisory capacity reached"} if capacity else {},
    ))


async def create_match(body, digest, user_id=None):
    now = utcnow()
    async with AsyncSessionLocal() as session, session.begin():
        # Serialize only this idempotency key, including races before the row exists.
        key = int.from_bytes(hashlib.sha256(str(body.request_id).encode()).digest()[:8], "big", signed=True)
        await session.execute(select(func.pg_advisory_xact_lock(key)))
        match = await session.scalar(select(FriendMatch).where(FriendMatch.create_request_id == str(body.request_id)))
        if match:
            match, seats = await locked_match(session, match.id)
            actor = authorize(seats, digest)
            if body.mode != match.mode or body.name != actor.name:
                fail("This request ID was already used with different details.")
        else:
            await admit_match(session, digest, now)
            match = make_match(body.mode, str(body.request_id), now)
            session.add(match)
            await session.flush()
            actor = make_seat(match, body.name, digest, str(uuid4()), now, 0, user_id)
            seats = [actor]
            session.add(actor)
            await session.flush()
        result = await snapshot(session, match, seats, actor, now)
    return result


async def invite(code):
    async with AsyncSessionLocal() as session:
        match = await session.scalar(select(FriendMatch).where(FriendMatch.invite_code == code))
        if not match:
            fail("Invite not found.", 404)
        names = (await session.scalars(select(FriendSeat.name).where(FriendSeat.match_id == match.id).order_by(FriendSeat.position))).all()
        return {"id": match.id, "invite_code": code, "mode": match.mode, "status": match.status,
                "players": [{"name": name} for name in names], "full": len(names) >= 2}


async def join_match(code, body, digest, user_id=None):
    now = utcnow()
    async with AsyncSessionLocal() as session, session.begin():
        match_id = await session.scalar(select(FriendMatch.id).where(FriendMatch.invite_code == code))
        if not match_id:
            fail("Invite not found.", 404)
        match, seats = await locked_match(session, match_id)
        actor = next((s for s in seats if s.credential_hash == digest), None)
        if not actor:
            if match.status != "lobby" or len(seats) >= 2:
                fail("This invite has no available seat.")
            used = await session.scalar(select(FriendSeat).where(FriendSeat.join_request_id == str(body.request_id)))
            if used:
                fail("This join request ID was already used.")
            recent = await session.scalar(select(func.count()).select_from(FriendSeat).join(
                FriendMatch, FriendMatch.id == FriendSeat.match_id).where(
                    FriendSeat.credential_hash == digest, FriendMatch.created_at >= now - timedelta(hours=1)))
            if recent >= 20:
                fail("Too many room joins in a short time. Please wait before joining another.", 429)
            actor = make_seat(match, body.name, digest, str(body.request_id), now, 1, user_id)
            session.add(actor)
            seats.append(actor)
            match.version += 1
        actor.last_seen_at = now
        await session.flush()
        result = await snapshot(session, match, seats, actor, now)
    return result


async def get_snapshot(match_id, digest):
    now = utcnow()
    async with AsyncSessionLocal() as session, session.begin():
        match, seats = await locked_match(session, match_id)
        actor = authorize(seats, digest)
        now = utcnow()
        await expire_locked(session, match, seats, now)
        actor.last_seen_at = now
        if start_if_ready(match, seats, now):
            match.version += 1
        result = await snapshot(session, match, seats, actor, now)
    return result


async def get_history(match_id, digest, before):
    async with AsyncSessionLocal() as session, session.begin():
        _, seats = await locked_match(session, match_id)
        actor = authorize(seats, digest)
        page = await history_page(session, match_id, before)
        question_ids = [row["id"] for row in page["history"] if row["type"] == "question"]
        jobs = (await session.scalars(select(FriendAdvisory).where(
            FriendAdvisory.question_id.in_(question_ids), FriendAdvisory.owner_id == actor.id
        ))).all() if question_ids else []
        page["guidance"] = [project_guidance(job, actor.id) for job in jobs]
        return page


async def canonical_entity(mode, action):
    if action.type not in {"select_secret", "randomize_secret", "guess"}:
        return None
    try:
        entities = await asyncio.to_thread(list_entities, mode)
    except Exception:
        fail("The entity list is temporarily unavailable.", 503)
    if not entities:
        fail("The entity list is temporarily unavailable.", 503)
    if action.type == "randomize_secret":
        return secrets.choice(entities)
    entity = next((e for e in entities if e["id"] == action.payload["entity_id"]), None)
    if entity is None:
        fail("Choose an entity from this mode's list.", 422)
    return entity


async def apply_action(match_id, digest, action: ActionRequest):
    # Read immutable mode, then release the connection before any provider work.
    async with AsyncSessionLocal() as session:
        mode = await session.scalar(select(FriendMatch.mode).where(FriendMatch.id == match_id))
        if not mode:
            fail("Match not found.", 404)
        seats = (await session.scalars(select(FriendSeat).where(FriendSeat.match_id == match_id))).all()
        actor = authorize(seats, digest)
        previous = await session.scalar(select(FriendAction).where(
            FriendAction.match_id == match_id, FriendAction.action_id == str(action.action_id)))
        if previous and (previous.player_id != actor.id or previous.payload_hash != action_hash(action)):
            fail("This action ID was already used for a different action.")
    if previous:
        return await get_snapshot(match_id, digest)
    entity = await canonical_entity(mode, action)
    now, expired = utcnow(), False
    async with AsyncSessionLocal() as session, session.begin():
        match, seats = await locked_match(session, match_id)
        now = utcnow()
        actor = authorize(seats, digest)
        previous = await session.scalar(select(FriendAction).where(
            FriendAction.match_id == match_id, FriendAction.action_id == str(action.action_id)))
        digest_body = action_hash(action)
        if previous:
            if previous.player_id != actor.id or previous.payload_hash != digest_body:
                fail("This action ID was already used for a different action.")
            return await snapshot(session, match, seats, actor, now)
        expired = await expire_locked(session, match, seats, now)
        if not expired:
            if match.version != action.expected_version:
                fail("The match changed. Refresh and try again.")
            if action.type == "rematch":
                require_admission()
            recent_actions = await session.scalar(select(func.count()).select_from(FriendAction).where(
                FriendAction.player_id == actor.id, FriendAction.created_at >= now - timedelta(minutes=1)))
            if recent_actions >= 120:
                fail("Actions are arriving too quickly. Please wait a moment.", 429)
            actor.last_seen_at = now
            move = None
            advisory = None
            if action.type in {"answer", "correct_answer"}:
                move = await session.scalar(select(FriendMove).where(
                    FriendMove.id == action.payload["question_id"], FriendMove.match_id == match_id))
                if move:
                    advisory = await session.get(FriendAdvisory, move.id)
            new_move = transition(match, seats, actor, action, now, entity=entity, move=move, advisory=advisory)
            if new_move:
                session.add(new_move)
                await session.flush()
                if new_move.type == "question":
                    await enqueue_advisory(session, new_move, now)
            if action.type == "rematch" and all(s.rematch_ready for s in seats):
                successor = await session.scalar(select(FriendMatch).where(FriendMatch.parent_id == match.id))
                if not successor:
                    await admit_match(session, digest, now)
                    successor = make_match(match.mode, str(uuid4()), now, parent_id=match.id)
                    session.add(successor)
                    await session.flush()
                    for old in seats:
                        session.add(make_seat(successor, old.name, old.credential_hash, str(uuid4()), now,
                                              1 - old.position, old.user_id))
            match.version += 1
            session.add(FriendAction(id=str(uuid4()), match_id=match_id, action_id=str(action.action_id),
                                     player_id=actor.id, payload_hash=digest_body, type=action.type,
                                     payload=action.payload, applied_version=match.version, created_at=now))
            await session.flush()
        result = await snapshot(session, match, seats, actor, now)
    if expired:
        fail("The turn expired before this action arrived. Refresh to see the current match.")
    return result


async def report_question(match_id, question_id, digest, comment):
    now = utcnow()
    async with AsyncSessionLocal() as session, session.begin():
        match, seats = await locked_match(session, match_id)
        actor = authorize(seats, digest)
        if match.status != "finished":
            fail("Reports are available after the match finishes.")
        move = await session.scalar(select(FriendMove).where(FriendMove.id == question_id,
            FriendMove.match_id == match_id, FriendMove.type == "question"))
        if not move:
            fail("Question not found.", 404)
        report = await session.scalar(select(FriendReport).where(
            FriendReport.question_id == question_id, FriendReport.reporter_id == actor.id))
        if report:
            fail("You have already reported this question.")
        job = await session.get(FriendAdvisory, question_id)
        report = FriendReport(id=str(uuid4()), question_id=question_id, reporter_id=actor.id,
                              comment=comment, created_at=now, details={
                                  "match_id": match_id, "mode": match.mode, "question": move.question,
                                  "target": move.target, "human_answer": move.answer, "revisions": move.revisions,
                                  "ai": admin_ai(job), "reported_revision": move.revision,
                              })
        session.add(report)
    return {"id": report.id, "status": "submitted"}


def comparison_expression():
    return case(
        (or_(FriendAdvisory.status.is_(None), FriendAdvisory.status == "failed"), "ai_unavailable"),
        (FriendAdvisory.status.in_(["pending", "running"]), "pending_ai"),
        (FriendAdvisory.answer == "INVALID", "ai_invalid"),
        (or_(FriendMove.answer.is_(None), FriendMove.answer.not_in(["yes", "no"])), "not_comparable"),
        (or_(and_(FriendMove.answer == "yes", FriendAdvisory.answer == "YES"),
             and_(FriendMove.answer == "no", FriendAdvisory.answer == "NO")), "agree"),
        else_="disagree",
    )


def admin_ai(job):
    if not job:
        return {"status": "failed", "answer": None, "explanation": None, "source": None,
                "completed_at": None, "evidence": {"error": "Advisory record missing"}}
    return {"status": job.status, "answer": job.answer, "explanation": job.explanation,
            "source": job.source, "completed_at": iso(job.completed_at), "interpretation": job.interpretation,
            "late": job.late, "evidence": job.evidence, "attempts": job.attempts, "error": job.error}


async def admin_questions(comparison, mode, offset, limit):
    async with AsyncSessionLocal() as session:
        label = comparison_expression()
        query = select(FriendMove, FriendMatch.mode, FriendAdvisory, label.label("comparison")).join(
            FriendMatch, FriendMatch.id == FriendMove.match_id).outerjoin(
            FriendAdvisory, FriendAdvisory.question_id == FriendMove.id).where(
                FriendMove.type == "question", FriendMatch.status == "finished")
        if mode:
            query = query.where(FriendMatch.mode == mode)
        if comparison != "all":
            query = query.where(label == comparison)
        total = await session.scalar(select(func.count()).select_from(query.subquery()))
        rows = (await session.execute(query.order_by(FriendMove.created_at.desc(), FriendMove.id).offset(offset).limit(limit))).all()
        ids = [row[0].id for row in rows]
        reports = (await session.scalars(select(FriendReport).where(FriendReport.question_id.in_(ids)))).all() if ids else []
        grouped = {}
        for report in reports:
            grouped.setdefault(report.question_id, []).append({"id": report.id, "reporter_id": report.reporter_id,
                "comment": report.comment, "created_at": iso(report.created_at), "details": report.details})
        return {"items": [{"id": m.id, "match_id": m.match_id, "mode": mode_name, "target": m.target,
                           "question": m.question, "human_answer": m.answer, "human_answered_at": iso(m.answered_at),
                           "revisions": m.revisions, "ai": admin_ai(job), "comparison": comparison_name,
                           "ai_seen_before_answer": m.ai_seen_before_answer, "review_status": m.review_status,
                           "review_note": m.review_note, "reviewed_at": iso(m.reviewed_at),
                           "reviewed_by": m.reviewed_by, "review_history": m.review_history,
                           "reports": grouped.get(m.id, [])} for m, mode_name, job, comparison_name in rows], "total": total}


async def review_question(question_id, body, reviewer_id):
    now = utcnow()
    async with AsyncSessionLocal() as session, session.begin():
        move = await session.scalar(select(FriendMove).join(
            FriendMatch, FriendMatch.id == FriendMove.match_id).where(
                FriendMove.id == question_id, FriendMove.type == "question",
                FriendMatch.status == "finished").with_for_update(of=FriendMove))
        if not move:
            fail("Question not found.", 404)
        move.review_status, move.review_note = body.status, body.note
        move.reviewed_by, move.reviewed_at = reviewer_id, now
        move.review_history = [*move.review_history, {"status": body.status, "note": body.note,
                                                    "reviewer_id": reviewer_id, "created_at": iso(now)}]
    return {"id": question_id, "review_status": body.status, "review_note": body.note, "reviewed_at": iso(now)}
