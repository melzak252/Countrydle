"""FastAPI endpoints for coat, flag, and regional symbol catalogs and assets."""

from __future__ import annotations

import asyncio
import gzip
import mimetypes
from typing import List, Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status

from powiatdle import flag_catalog
from powiatdle.heraldry_pkg.assets import (
    accepts_gzip,
    compressed_regional_asset,
    flag_asset_url,
    get_daily_herb_preview,
    get_or_fetch_herb_svg,
    regional_asset_url,
    source_attribution,
    thumbnail_credit,
    thumbnail_entry,
    thumbnail_response,
    thumbnail_url,
)
from powiatdle.heraldry_pkg.catalog import (
    entity_scope,
    get_all_counties,
    get_county_by_id,
    polish_sort_key,
    require_token_mode,
    require_token_scope,
    symbol_mode,
)
from powiatdle.heraldry_pkg.schemas import (
    PowiatHeraldryItem,
    decrypt_session_token,
    facade_attr,
)
from regional_symbols import catalog as regional_catalog


async def get_coat_asset(
    token: str = Query(...),
    full: bool = Query(False),
    accept_encoding: str = Header(default=""),
):
    """Serve an opaque daily preview, or the original on inspection."""
    payload = decrypt_session_token(token)
    require_token_mode(payload, "coat")
    require_token_scope(payload, "county")
    target_id = payload.get("target_id")
    if not target_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing target in token.",
        )
    county = facade_attr("get_county_by_id", get_county_by_id)(target_id)
    if not county:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target county not found.",
        )

    if full:
        fetch_svg = facade_attr("get_or_fetch_herb_svg", get_or_fetch_herb_svg)
        data = await asyncio.to_thread(fetch_svg, target_id, county["name"])
        media_type = "image/svg+xml"
    else:
        fetch_preview = facade_attr("get_daily_herb_preview", get_daily_herb_preview)
        data, media_type = await asyncio.to_thread(fetch_preview, target_id, county["name"])
    headers = {"Cache-Control": "private, no-store"}
    if media_type == "image/svg+xml":
        headers["Vary"] = "Accept-Encoding"
        if accepts_gzip(accept_encoding):
            data = await asyncio.to_thread(gzip.compress, data, compresslevel=3, mtime=0)
            headers["Content-Encoding"] = "gzip"
    return Response(content=data, media_type=media_type, headers=headers)


async def flag_county_catalog():
    catalog = flag_catalog.load_catalog()
    counties = [c for c in facade_attr("get_all_counties", get_all_counties)() if c["id"] in catalog]
    if not counties:
        raise HTTPException(status_code=503, detail="Flag catalog unavailable.")
    counties.sort(key=lambda c: polish_sort_key(c["name"]))
    thumbs_dir = flag_catalog.ASSET_DIR.parent / "flag_thumbnails"
    return [
        {
            "id": c["id"],
            "name": c["name"],
            "voivodeship": c["voivodeship"],
            "is_city_county": c["is_city_county"],
            "flag_asset_url": flag_asset_url(c["id"], catalog[c["id"]]),
            "thumbnail_asset_url": thumbnail_url(
                thumbs_dir,
                "flag",
                c["id"],
                catalog[c["id"]],
                "/powiatdle/flags",
                flag_asset_url(c["id"], catalog[c["id"]]),
            ),
            "source_attribution": thumbnail_credit(
                source_attribution("flag", c),
                bool(thumbnail_entry(thumbs_dir, "flag", c["id"], catalog[c["id"]])),
            ),
        }
        for c in counties
    ]


async def flag_thumbnail(county_id: int, v: str = Query(...)):
    record = flag_catalog.load_catalog().get(county_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Flag not found.")
    return await thumbnail_response(
        flag_catalog.ASSET_DIR.parent / "flag_thumbnails", "flag", county_id, record, v
    )


async def flag_asset(
    county_id: int,
    v: Optional[str] = Query(None),
    accept_encoding: str = Header(default=""),
):
    catalog = flag_catalog.load_catalog()
    record = catalog.get(county_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Flag not found.")
    version = record["source"].get("asset_sha1") or record["source"].get("sha1")
    if v is not None and v != version:
        raise HTTPException(status_code=404, detail="Flag version not found.")
    path = flag_catalog.ASSET_DIR / record["filename"]
    try:
        data = await asyncio.to_thread(path.read_bytes)
    except OSError:
        raise HTTPException(status_code=503, detail="Flag asset unavailable.")
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    headers = {
        "Cache-Control": (
            "public, max-age=31536000, immutable" if version and v == version else "no-cache"
        )
    }
    if media_type == "image/svg+xml":
        headers["Vary"] = "Accept-Encoding"
        if accepts_gzip(accept_encoding):
            data = await asyncio.to_thread(gzip.compress, data, compresslevel=3, mtime=0)
            headers["Content-Encoding"] = "gzip"
    return Response(content=data, media_type=media_type, headers=headers)


async def flag_session_asset(
    token: str = Query(...),
    full: bool = Query(False),
    accept_encoding: str = Header(default=""),
):
    payload = decrypt_session_token(token)
    require_token_mode(payload, "flag")
    require_token_scope(payload, "county")
    target_id = payload.get("target_id")
    catalog = flag_catalog.load_catalog()
    if type(target_id) is not int or target_id not in catalog:
        raise HTTPException(status_code=403, detail="Flag target is not in the catalog.")
    directory = flag_catalog.ASSET_DIR.parent / "flag_previews"
    entry = thumbnail_entry(directory, "flag", target_id, catalog[target_id])
    if entry and not full:
        try:
            response = await thumbnail_response(
                directory, "flag", target_id, catalog[target_id], entry["sha256"]
            )
        except HTTPException as exc:
            if exc.status_code != 503:
                raise
            response = await flag_asset(target_id, v=None, accept_encoding=accept_encoding)
    else:
        response = await flag_asset(target_id, v=None, accept_encoding=accept_encoding)
    response.headers["Cache-Control"] = "private, no-store"
    return response


async def regional_symbol_catalog(request: Request):
    scope, mode = entity_scope(request), symbol_mode(request)
    records = regional_catalog.load_catalog(scope, mode)
    entities = regional_catalog.load_entities(scope)
    thumbs_dir = regional_catalog.DATA_ROOT / scope / "thumbnails"
    return [
        {
            "id": entity["id"],
            "name": entity["name"],
            "aliases": entity["aliases"],
            "voivodeship": "",
            "is_city_county": False,
            "flag_asset_url": regional_asset_url(scope, mode, entity["id"], records[entity["id"]]),
            "thumbnail_asset_url": thumbnail_url(
                thumbs_dir,
                mode,
                entity["id"],
                records[entity["id"]],
                f"/regional-symbols/{scope}/{mode}",
                regional_asset_url(scope, mode, entity["id"], records[entity["id"]]),
            ),
            "source_attribution": thumbnail_credit(
                source_attribution(mode, entity, scope),
                bool(thumbnail_entry(thumbs_dir, mode, entity["id"], records[entity["id"]])),
            ),
        }
        for entity in sorted((entities[id_] for id_ in records), key=lambda e: e["name"].casefold())
    ]


async def regional_thumbnail(request: Request, entity_id: int, v: str = Query(...)):
    scope, mode = entity_scope(request), symbol_mode(request)
    record = regional_catalog.load_catalog(scope, mode).get(entity_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Symbol not found.")
    return await thumbnail_response(
        regional_catalog.DATA_ROOT / scope / "thumbnails", mode, entity_id, record, v
    )


async def regional_asset(
    request: Request,
    entity_id: int,
    v: Optional[str] = Query(None),
    accept_encoding: str = Header(default=""),
):
    scope, mode = entity_scope(request), symbol_mode(request)
    record = regional_catalog.load_catalog(scope, mode).get(entity_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Symbol not found.")
    version = record["source"].get("asset_sha1") or record["source"].get("sha1")
    if v is not None and v != version:
        raise HTTPException(status_code=404, detail="Symbol version not found.")
    path = regional_catalog.DATA_ROOT / scope / "assets" / record["filename"]
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    headers = {
        "Cache-Control": (
            "public, max-age=31536000, immutable" if version and v == version else "no-cache"
        )
    }
    compress = media_type == "image/svg+xml" and accepts_gzip(accept_encoding)
    try:
        if compress and version:
            data = await asyncio.to_thread(compressed_regional_asset, path, str(version))
        else:
            data = await asyncio.to_thread(path.read_bytes)
            if compress:
                data = await asyncio.to_thread(gzip.compress, data, compresslevel=3, mtime=0)
    except OSError:
        raise HTTPException(status_code=503, detail="Symbol asset unavailable.")
    if media_type == "image/svg+xml":
        headers["Vary"] = "Accept-Encoding"
        if compress:
            headers["Content-Encoding"] = "gzip"
    return Response(content=data, media_type=media_type, headers=headers)


async def regional_session_asset(
    request: Request,
    token: str = Query(...),
    full: bool = Query(False),
    accept_encoding: str = Header(default=""),
):
    scope, mode = entity_scope(request), symbol_mode(request)
    payload = decrypt_session_token(token)
    require_token_scope(payload, scope)
    require_token_mode(payload, mode)
    target_id = payload.get("target_id")
    records = regional_catalog.load_catalog(scope, mode)
    if type(target_id) is not int or target_id not in records:
        raise HTTPException(status_code=403, detail="Symbol target is not in the catalog.")
    record = records[target_id]
    directory = regional_catalog.DATA_ROOT / scope / "previews"
    entry = thumbnail_entry(directory, mode, target_id, record)
    if entry and not full:
        try:
            response = await thumbnail_response(directory, mode, target_id, record, entry["sha256"])
        except HTTPException as exc:
            if exc.status_code != 503:
                raise
            response = await regional_asset(request, target_id, v=None, accept_encoding=accept_encoding)
    else:
        response = await regional_asset(request, target_id, v=None, accept_encoding=accept_encoding)
    response.headers["Cache-Control"] = "private, no-store"
    return response


def register_asset_routes(
    router: APIRouter,
    flag_router: APIRouter,
    regional_router: APIRouter,
    get_counties_fn,
) -> None:
    async def flag_counties():
        flag_catalog.load_catalog()
        return await get_counties_fn()

    router.add_api_route("/coat-asset", get_coat_asset, methods=["GET"])

    flag_router.add_api_route(
        "/counties", flag_counties, methods=["GET"], response_model=List[PowiatHeraldryItem]
    )
    flag_router.add_api_route("/catalog", flag_county_catalog, methods=["GET"])
    flag_router.add_api_route("/thumbnails/{county_id}", flag_thumbnail, methods=["GET"])
    flag_router.add_api_route("/assets/{county_id}", flag_asset, methods=["GET"])
    flag_router.add_api_route("/flag-asset", flag_session_asset, methods=["GET"])

    regional_router.add_api_route("/catalog", regional_symbol_catalog, methods=["GET"])
    regional_router.add_api_route("/thumbnails/{entity_id}", regional_thumbnail, methods=["GET"])
    regional_router.add_api_route("/assets/{entity_id}", regional_asset, methods=["GET"])
    regional_router.add_api_route("/session-asset", regional_session_asset, methods=["GET"])
