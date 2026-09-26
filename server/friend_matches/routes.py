import asyncio
import logging
import os
import re
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from sqlalchemy.exc import IntegrityError

from db import AsyncSessionLocal
from db.repositories.user import UserRepository
from users.utils import get_admin_user, verify_access_token
from . import service
from .providers import list_entities
from .schemas import ActionRequest, Comparison, CreateRequest, JoinRequest, Mode, ReportRequest, ReviewRequest

router = APIRouter(tags=["friend-matches"])
logger = logging.getLogger(__name__)
COOKIE_NAME = "friend_duel_seat"
COOKIE_AGE = 60 * 60 * 24 * 365
DEFAULT_ORIGINS = {
    "http://localhost", "http://localhost:80", "http://localhost:5173", "http://localhost:5174",
    "http://127.0.0.1", "http://127.0.0.1:80", "http://127.0.0.1:5173", "http://127.0.0.1:5174",
    "https://jmelzacki.com", "https://www.jmelzacki.com",
}


def require_origin(connection, *, required=True):
    origin = connection.headers.get("origin")
    if not origin and not required:
        return
    scheme = connection.url.scheme.replace("wss", "https").replace("ws", "http")
    same_origin = f"{scheme}://{connection.headers.get('host', '')}"
    configured = {value.strip().rstrip("/") for value in os.getenv("FRIEND_ALLOWED_ORIGINS", "").split(",") if value.strip()}
    if not origin or origin == "null" or origin not in DEFAULT_ORIGINS | configured | {same_origin}:
        raise HTTPException(status_code=403, detail="This origin is not allowed to access friend duels.")


def guest_token(connection):
    token = connection.cookies.get(COOKIE_NAME, "")
    return token if re.fullmatch(r"[A-Za-z0-9_-]{43}", token) else None


def seat_digest(connection):
    token = guest_token(connection)
    if not token:
        raise HTTPException(status_code=403, detail="This browser does not have a seat in this match.")
    return service.credential_hash(token)


def admission_digest(request):
    if not guest_token(request):
        raise HTTPException(status_code=409, detail={
            "code": "friend_session_required",
            "message": "Initialize this browser's friend session before creating or joining a match.",
        })
    return seat_digest(request)


def issue_guest(request, response):
    token = guest_token(request) or secrets.token_urlsafe(32)
    configured = os.getenv("FRIEND_COOKIE_SECURE")
    secure = configured.lower() in {"true", "1", "yes"} if configured is not None else request.url.scheme == "https"
    response.set_cookie(COOKIE_NAME, token, httponly=True, secure=secure, samesite="lax",
                        path="/", max_age=COOKIE_AGE)
    # Path=/ is required: existing proxies strip the public /api prefix.
    return service.credential_hash(token)


async def optional_user_id(request):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        email = verify_access_token(token)
    except HTTPException:
        return None
    async with AsyncSessionLocal() as session:
        user = await UserRepository(session).get_by_email(email)
        return user.id if user else None


def private_response(request, response):
    require_origin(request, required=False)
    response.headers["Cache-Control"] = "no-store"


@router.get("/friend-matches/entities")
async def entities(mode: Mode):
    try:
        return {"entities": await asyncio.to_thread(list_entities, mode)}
    except Exception:
        logger.exception("Friend duel entity list unavailable for %s", mode)
        raise HTTPException(status_code=503, detail="This mode's entity list is temporarily unavailable.")


@router.post("/friend-matches/session")
async def initialize_session(request: Request, response: Response):
    require_origin(request)
    response.headers["Cache-Control"] = "no-store"
    issue_guest(request, response)
    return {"ready": True}


@router.post("/friend-matches")
async def create(body: CreateRequest, request: Request, response: Response):
    require_origin(request)
    response.headers["Cache-Control"] = "no-store"
    digest = admission_digest(request)
    return await service.create_match(body, digest, await optional_user_id(request))


@router.get("/friend-matches/invites/{code}")
async def preview(code: str, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return await service.invite(code)


@router.post("/friend-matches/invites/{code}/join")
async def join(code: str, body: JoinRequest, request: Request, response: Response):
    require_origin(request)
    response.headers["Cache-Control"] = "no-store"
    digest = admission_digest(request)
    try:
        return await service.join_match(code, body, digest, await optional_user_id(request))
    except IntegrityError:
        raise HTTPException(status_code=409, detail="This join request was already used. Refresh the match.")



@router.get("/friend-matches/{match_id}")
async def view(match_id: UUID, request: Request, response: Response):
    private_response(request, response)
    return await service.get_snapshot(str(match_id), seat_digest(request))


@router.get("/friend-matches/{match_id}/history")
async def history(match_id: UUID, request: Request, response: Response, before: int | None = Query(None, ge=1)):
    private_response(request, response)
    return await service.get_history(str(match_id), seat_digest(request), before)


@router.post("/friend-matches/{match_id}/actions")
async def act(match_id: UUID, body: ActionRequest, request: Request, response: Response):
    require_origin(request)
    response.headers["Cache-Control"] = "no-store"
    return await service.apply_action(str(match_id), seat_digest(request), body)


@router.post("/friend-matches/{match_id}/questions/{question_id}/reports")
async def report(match_id: UUID, question_id: UUID, body: ReportRequest, request: Request, response: Response):
    require_origin(request)
    response.headers["Cache-Control"] = "no-store"
    return await service.report_question(str(match_id), str(question_id), seat_digest(request), body.comment)


@router.websocket("/friend-matches/{match_id}/ws")
async def socket(websocket: WebSocket, match_id: UUID):
    try:
        require_origin(websocket)
        digest = seat_digest(websocket)
        state = await service.get_snapshot(str(match_id), digest)
    except HTTPException:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    try:
        while True:
            # Per-viewer reads see commits from any app process, including AI-only updates.
            await asyncio.wait_for(websocket.send_json(state), timeout=5)
            try:
                event = await asyncio.wait_for(websocket.receive(), timeout=1)
                if event["type"] == "websocket.disconnect":
                    return
            except asyncio.TimeoutError:
                pass
            state = await service.get_snapshot(str(match_id), digest)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        return
    except HTTPException:
        await websocket.close(code=1008)
    except Exception:
        logger.exception("Friend duel socket could not refresh %s", match_id)
        await websocket.close(code=1011)


@router.get("/admin/friend-matches/questions")
async def question_review_list(request: Request, response: Response,
                               comparison: Comparison = "all", mode: Mode | None = None,
                               offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=100),
                               admin=Depends(get_admin_user)):
    private_response(request, response)
    return await service.admin_questions(comparison, mode, offset, limit)


@router.patch("/admin/friend-matches/questions/{question_id}")
async def question_review(question_id: UUID, body: ReviewRequest, request: Request,
                          response: Response, admin=Depends(get_admin_user)):
    require_origin(request)
    response.headers["Cache-Control"] = "no-store"
    return await service.review_question(str(question_id), body, admin.id)
