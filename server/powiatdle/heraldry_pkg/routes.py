"""FastAPI routers and daily/challenge/guess/sync/leaderboard endpoints for heraldry & flags."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models.user import User
from powiatdle import flag_catalog, heraldry_daily
from powiatdle.heraldry_pkg.asset_routes import register_asset_routes
from powiatdle.heraldry_pkg.assets import asset_url, reconstruct_guesses, source_attribution
from powiatdle.heraldry_pkg.catalog import (
    bearing_between,
    distance_between,
    entities_for,
    entity_by_id,
    entity_scope,
    get_all_counties,
    get_registration_plates,
    polish_sort_key,
    regional_target,
    require_token_mode,
    require_token_scope,
    resolve_entity,
    select_target,
    symbol_mode,
)
from powiatdle.heraldry_pkg.schemas import (
    PowiatHeraldryChallenge,
    PowiatHeraldryGuessRequest,
    PowiatHeraldryGuessResult,
    PowiatHeraldryItem,
    PowiatHeraldryTarget,
    RegionalSymbolItem,
    decrypt_session_token,
    encrypt_session_token,
    facade_attr,
)
from powiatdle.heraldry_quiz import flags_quiz_router, regional_quiz_router, router as quiz_router
from regional_symbols import catalog as regional_catalog
from users.utils import get_current_or_guest_user, get_current_user

router = APIRouter(prefix="/heraldry", tags=["powiat-heraldry"])
router.include_router(quiz_router)
flag_router = APIRouter(prefix="/flags", tags=["powiat-flags"])
regional_router = APIRouter(prefix="/regional-symbols/{scope}/{mode}", tags=["regional-symbols"])


@router.get("/counties", response_model=List[PowiatHeraldryItem])
async def get_counties():
    """Returns catalog of all counties sorted alphabetically by name."""
    counties = facade_attr("get_all_counties", get_all_counties)()
    counties.sort(key=lambda c: polish_sort_key(c["name"]))
    return [
        PowiatHeraldryItem(
            id=c["id"],
            name=c["name"],
            voivodeship=c["voivodeship"],
            is_city_county=c["is_city_county"],
        )
        for c in counties
    ]


@regional_router.get("/counties", response_model=List[RegionalSymbolItem])
async def regional_entities(request: Request):
    scope, mode = entity_scope(request), symbol_mode(request)
    regional_catalog.load_catalog(scope, mode)
    return [
        RegionalSymbolItem(
            id=e["id"],
            name=e["name"],
            aliases=e["aliases"],
            voivodeship="",
            is_city_county=False,
        )
        for e in sorted(entities_for(scope), key=lambda entity: entity["name"].casefold())
    ]


@router.get("/challenge", response_model=PowiatHeraldryChallenge)
async def get_challenge(
    request: Request,
    response: Response,
    seed: Optional[str] = Query(None),
    token: Optional[str] = Query(None),
    user: Optional[User] = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    """Retrieves or restores a heraldry challenge (daily or custom seed)."""
    mode, scope = symbol_mode(request), entity_scope(request)
    all_counties = entities_for(scope)
    if not all_counties:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No counties catalog available.",
        )

    today_str = datetime.now(timezone.utc).date().isoformat()
    if not seed or seed.strip() in {"daily", f"daily-{today_str}"}:
        is_daily = True
        effective_seed = f"daily-{today_str}"
    else:
        is_daily = False
        effective_seed = seed.strip()[:64]

    target_county = (
        select_target(all_counties, effective_seed, mode)
        if scope == "county"
        else regional_target(scope, mode, effective_seed)
    )
    target_id = target_county["id"]

    ranked_row = None
    parsed_token = None
    if token:
        try:
            parsed_token = decrypt_session_token(token)
        except HTTPException:
            token = None
    if parsed_token:
        require_token_mode(parsed_token, mode)
        require_token_scope(parsed_token, scope)
    if (
        is_daily
        and parsed_token
        and parsed_token.get("session_id")
        and parsed_token.get("seed") == effective_seed
    ):
        ranked_row = await heraldry_daily.get_owned_daily(
            session, request, user, parsed_token["session_id"], symbol_mode=mode, entity_scope=scope
        )
        token = encrypt_session_token(heraldry_daily.token_payload(ranked_row))
    elif is_daily and (not parsed_token or parsed_token.get("seed") != effective_seed):
        ranked_row = await heraldry_daily.get_or_create_daily(
            session,
            request,
            response,
            user,
            datetime.now(timezone.utc).date(),
            target_county,
            symbol_mode=mode,
            entity_scope=scope,
        )
        token = encrypt_session_token(heraldry_daily.token_payload(ranked_row))

    if token:
        try:
            payload = decrypt_session_token(token)
            if payload.get("seed") == effective_seed:
                payload_target_id = payload.get("target_id", target_id)
                target = entity_by_id(scope, payload_target_id) or target_county
                guesses_ids = payload.get("guesses", [])
                reconstructed_guesses = reconstruct_guesses(payload, target, scope, mode, ranked_row)

                won = any(gid == target["id"] for gid in guesses_ids)
                is_game_over = won or (len(guesses_ids) >= 8)
                wrong_guesses = [gid for gid in guesses_ids if gid != target["id"]]

                registration_plates = None
                if scope == "county" and (len(wrong_guesses) >= 5 or is_game_over):
                    registration_plates = facade_attr(
                        "get_registration_plates", get_registration_plates
                    )(target["id"])

                target_powiat_obj = None
                source_attr = None
                if is_game_over:
                    target_powiat_obj = PowiatHeraldryTarget(
                        id=target["id"],
                        name=target["name"],
                        voivodeship=target["voivodeship"],
                    )
                    source_attr = source_attribution(mode, target, scope)

                return PowiatHeraldryChallenge(
                    seed=effective_seed,
                    is_daily=is_daily,
                    date=payload.get("date", today_str),
                    max_guesses=8,
                    hint_unlock_guesses=5,
                    token=token,
                    coat_asset_url=asset_url(mode, target["id"], token, scope),
                    source_attribution=source_attr,
                    guesses=reconstructed_guesses,
                    is_game_over=is_game_over,
                    won=won,
                    registration_plates=registration_plates,
                    target_powiat=target_powiat_obj,
                    ranked=ranked_row is not None,
                    points=ranked_row.points if ranked_row is not None else None,
                )
        except HTTPException:
            pass

    fresh_payload = {
        "seed": effective_seed,
        "is_daily": is_daily,
        "date": today_str,
        "target_id": target_id,
        "symbol_mode": mode,
        **({"entity_scope": scope} if scope != "county" else {}),
        "guesses": [],
    }
    fresh_token = encrypt_session_token(fresh_payload)

    return PowiatHeraldryChallenge(
        seed=effective_seed,
        is_daily=is_daily,
        date=today_str,
        max_guesses=8,
        hint_unlock_guesses=5,
        token=fresh_token,
        coat_asset_url=asset_url(mode, target_id, fresh_token, scope),
        source_attribution=None,
        guesses=[],
        is_game_over=False,
        won=False,
        registration_plates=None,
        target_powiat=None,
    )


@router.post("/guess", response_model=PowiatHeraldryGuessResult)
async def make_guess(
    body: PowiatHeraldryGuessRequest,
    request: Request,
    user: Optional[User] = Depends(get_current_or_guest_user),
    session: AsyncSession = Depends(get_db),
):
    """Evaluates a guess in Powiat Heraldry mode."""
    payload = decrypt_session_token(body.token)
    mode, scope = symbol_mode(request), entity_scope(request)
    require_token_mode(payload, mode)
    require_token_scope(payload, scope)
    target_id = payload.get("target_id")
    if scope != "county" and target_id not in regional_catalog.load_catalog(scope, mode):
        raise HTTPException(status_code=403, detail="Symbol target is not in the catalog.")
    if scope == "county" and mode == "flag" and target_id not in flag_catalog.load_catalog():
        raise HTTPException(status_code=403, detail="Flag target is not in the catalog.")
    target_county = entity_by_id(scope, target_id)
    if not target_county:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target county not found.",
        )

    guesses: list[int] = payload.get("guesses", [])
    if target_id in guesses or len(guesses) >= 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The game is already over.",
        )

    guessed_county = resolve_entity(scope, body.guess, body.powiat_id)
    if not guessed_county:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown county: '{body.guess}'.",
        )

    guessed_id = guessed_county["id"]
    if guessed_id in guesses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This county has already been checked.",
        )
    ranked_row = None
    if payload.get("session_id"):
        ranked_row = await heraldry_daily.record_guess(
            session, request, user, payload, guessed_county, symbol_mode=mode, entity_scope=scope
        )

    guesses.append(guessed_id)
    payload["guesses"] = guesses
    guesses_made = len(guesses)
    remaining_guesses = max(0, 8 - guesses_made)

    is_correct = guessed_id == target_id
    won = is_correct
    is_game_over = won or (guesses_made >= 8)

    same_voivodeship = (
        scope == "county"
        and guessed_county["voivodeship"].strip().lower()
        == target_county["voivodeship"].strip().lower()
    )

    if is_correct:
        distance_km, bearing_degrees, bearing_direction, bearing_arrow = 0, None, None, None
    else:
        distance_km = distance_between(scope, guessed_county, target_county)
        bearing_degrees, bearing_direction, bearing_arrow = bearing_between(
            scope, guessed_county, target_county
        )

    if scope == "county" and ((not is_correct and guesses_made >= 5) or is_game_over):
        registration_plates = facade_attr("get_registration_plates", get_registration_plates)(
            target_id
        )
    else:
        registration_plates = None

    target_powiat_obj = None
    source_attr = None
    if is_game_over:
        target_powiat_obj = PowiatHeraldryTarget(
            id=target_county["id"],
            name=target_county["name"],
            voivodeship=target_county["voivodeship"],
        )
        source_attr = source_attribution(mode, target_county, scope)

    new_token = encrypt_session_token(payload)

    return PowiatHeraldryGuessResult(
        answer=is_correct,
        guess=guessed_county["name"],
        powiat_id=guessed_id,
        voivodeship=guessed_county["voivodeship"],
        distance_km=distance_km,
        bearing_degrees=bearing_degrees,
        bearing_direction=bearing_direction,
        bearing_arrow=bearing_arrow,
        same_voivodeship=same_voivodeship,
        guesses_made=guesses_made,
        remaining_guesses=remaining_guesses,
        is_game_over=is_game_over,
        won=won,
        registration_plates=registration_plates,
        target_powiat=target_powiat_obj,
        source_attribution=source_attr,
        ranked=ranked_row is not None,
        points=ranked_row.points if ranked_row is not None else None,
        token=new_token,
    )


@router.post("/sync", response_model=PowiatHeraldryChallenge)
async def sync_daily(
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    mode, scope = symbol_mode(request), entity_scope(request)
    if scope != "county":
        regional_catalog.load_catalog(scope, mode)
    elif mode == "flag":
        flag_catalog.load_catalog()
    row = await heraldry_daily.claim_daily(
        session, request, user, symbol_mode=mode, entity_scope=scope
    )
    token = encrypt_session_token(heraldry_daily.token_payload(row))
    return await get_challenge(
        request=request, response=response, seed=None, token=token, user=user, session=session
    )


@router.get("/leaderboard")
async def daily_leaderboard(
    request: Request,
    type: str = Query("monthly"),
    session: AsyncSession = Depends(get_db),
):
    mode, scope = symbol_mode(request), entity_scope(request)
    if scope != "county":
        regional_catalog.load_catalog(scope, mode)
    elif mode == "flag":
        flag_catalog.load_catalog()
    return await heraldry_daily.leaderboard(session, type, symbol_mode=mode, entity_scope=scope)


register_asset_routes(router, flag_router, regional_router, get_counties)

regional_router.add_api_route(
    "/challenge", get_challenge, methods=["GET"], response_model=PowiatHeraldryChallenge
)
regional_router.add_api_route(
    "/guess", make_guess, methods=["POST"], response_model=PowiatHeraldryGuessResult
)
regional_router.add_api_route(
    "/sync", sync_daily, methods=["POST"], response_model=PowiatHeraldryChallenge
)
regional_router.add_api_route("/leaderboard", daily_leaderboard, methods=["GET"])

flag_router.add_api_route(
    "/challenge", get_challenge, methods=["GET"], response_model=PowiatHeraldryChallenge
)
flag_router.add_api_route(
    "/guess", make_guess, methods=["POST"], response_model=PowiatHeraldryGuessResult
)
flag_router.add_api_route(
    "/sync", sync_daily, methods=["POST"], response_model=PowiatHeraldryChallenge
)
flag_router.add_api_route("/leaderboard", daily_leaderboard, methods=["GET"])

flag_router.include_router(flags_quiz_router)
regional_router.include_router(regional_quiz_router)
