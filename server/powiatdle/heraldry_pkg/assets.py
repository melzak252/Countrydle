"""Thumbnail/SVG/PNG/WebP serving, caching, attribution, and gzip helpers."""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import io
import json
import logging
import re
import threading
import urllib.parse
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Response, status
from PIL import Image

from powiatdle import flag_catalog
from powiatdle.heraldry_pkg.catalog import (
    get_heraldry_filename,
    get_herb_cache_dir,
    heraldry_cache_path,
)
from powiatdle.heraldry_pkg.schemas import (
    PowiatHeraldrySourceAttribution,
    RegionalSourceAttribution,
    facade_attr,
)
from powiatdle.heraldry_pkg.wikimedia import (
    atomic_write,
    fetch_url,
    read_heraldry_cache,
    resolve_and_fetch_heraldry,
    write_heraldry_cache,
)
from regional_symbols import catalog as regional_catalog

logger = logging.getLogger("countrydle.powiatdle.heraldry")


def get_or_fetch_herb_svg(powiat_id: int, powiat_name: str) -> bytes:
    cache_file = heraldry_cache_path(facade_attr("get_herb_cache_dir", get_herb_cache_dir)(), powiat_id)
    try:
        return read_heraldry_cache(cache_file)[0]
    except (OSError, ValueError, KeyError, TypeError):
        pass

    try:
        svg_bytes, meta = facade_attr("resolve_and_fetch_heraldry", resolve_and_fetch_heraldry)(
            powiat_name, facade_attr("get_heraldry_filename", get_heraldry_filename)(powiat_id)
        )
        write_heraldry_cache(cache_file, svg_bytes, meta)
        return svg_bytes
    except Exception as exc:
        try:
            return read_heraldry_cache(cache_file)[0]
        except (OSError, ValueError, KeyError, TypeError):
            pass
        logger.warning(
            "Failed to fetch coat of arms for powiat %s (%s): %s", powiat_id, powiat_name, exc
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Coat of arms asset temporarily unavailable.",
        ) from exc


def get_or_fetch_herb_thumb(
    powiat_id: int, powiat_name: str, width: int = 80
) -> tuple[bytes, str]:
    """Return a source-bound PNG thumbnail or the original SVG."""
    root = facade_attr("get_herb_cache_dir", get_herb_cache_dir)()
    cached_svg = None
    try:
        cached_svg, metadata = read_heraldry_cache(heraldry_cache_path(root, powiat_id))
        filename = metadata.get("filename")
    except (OSError, ValueError, KeyError, TypeError):
        filename = None
    filename = filename or facade_attr("get_heraldry_filename", get_heraldry_filename)(powiat_id)
    if filename:
        cache_dir = root / "thumbs"
        source_key = hashlib.sha256(filename.encode("utf-8")).hexdigest()[:16]
        thumb_file = cache_dir / f"thumb_{width}_{powiat_id}_{source_key}.png"
        try:
            data = thumb_file.read_bytes()
            if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 64:
                return data, "image/png"
        except OSError:
            pass
        thumb_url = (
            f"https://commons.wikimedia.org/wiki/Special:FilePath/"
            f"{urllib.parse.quote(filename)}?width={width}"
        )
        try:
            png_bytes = facade_attr("fetch_url", fetch_url)(thumb_url)
            if png_bytes.startswith(b"\x89PNG\r\n\x1a\n") and len(png_bytes) >= 64:
                facade_attr("atomic_write", atomic_write)(thumb_file, png_bytes)
                return png_bytes, "image/png"
        except Exception as exc:
            logger.warning("Thumbnail fetch failed for powiat %s (%s): %s", powiat_id, filename, exc)
    if cached_svg is not None:
        return cached_svg, "image/svg+xml"
    return facade_attr("get_or_fetch_herb_svg", get_or_fetch_herb_svg)(powiat_id, powiat_name), "image/svg+xml"


@lru_cache(maxsize=512)
def daily_preview_lock(powiat_id: int):
    return threading.Lock()


@lru_cache(maxsize=512)
def cached_heraldry_source(path: Path, identity: tuple[int, int, int, int, int]) -> Optional[str]:
    # The fingerprint invalidates the parsed metadata whenever the atomic cache changes.
    _, metadata = read_heraldry_cache(path)
    return metadata.get("filename")


def get_daily_herb_preview(powiat_id: int, powiat_name: str) -> tuple[bytes, str]:
    """Cache a bounded rendition from the same source as the original and its credit."""
    with daily_preview_lock(powiat_id):
        root = facade_attr("get_herb_cache_dir", get_herb_cache_dir)()
        cache_file = heraldry_cache_path(root, powiat_id)
        try:
            stat = cache_file.stat()
            identity = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
            filename = cached_heraldry_source(cache_file, identity)
        except (OSError, ValueError, KeyError, TypeError):
            filename = None
        filename = filename or facade_attr("get_heraldry_filename", get_heraldry_filename)(powiat_id)
        if isinstance(filename, str) and filename:
            source_key = hashlib.sha256(filename.encode("utf-8")).hexdigest()[:16]
            path = root / "thumbs" / f"daily_512_{powiat_id}_{source_key}.webp"
            try:
                data = path.read_bytes()
                if len(data) >= 20 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
                    return data, "image/webp"
            except OSError:
                pass
            url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{urllib.parse.quote(filename)}?width=512"
            try:
                source = facade_attr("fetch_url", fetch_url)(url)
                with Image.open(io.BytesIO(source)) as image:
                    if image.format != "PNG":
                        raise ValueError("Thumbnail source is not PNG")
                    image.thumbnail((512, 512), Image.Resampling.LANCZOS)
                    output = io.BytesIO()
                    image.save(output, format="WEBP", quality=85, method=4, exact=True)
                data = output.getvalue()
                facade_attr("atomic_write", atomic_write)(path, data)
                return data, "image/webp"
            except (OSError, ValueError, RuntimeError) as exc:
                logger.warning("Daily thumbnail unavailable for powiat %s: %s", powiat_id, exc)
        return facade_attr("get_or_fetch_herb_svg", get_or_fetch_herb_svg)(powiat_id, powiat_name), "image/svg+xml"


def get_source_attribution(
    powiat_id: int, powiat_name: Optional[str] = None
) -> Optional[PowiatHeraldrySourceAttribution]:
    cache_file = heraldry_cache_path(facade_attr("get_herb_cache_dir", get_herb_cache_dir)(), powiat_id)
    try:
        _, metadata = read_heraldry_cache(cache_file)
    except (OSError, ValueError, KeyError, TypeError):
        if not powiat_name:
            return None
        try:
            facade_attr("get_or_fetch_herb_svg", get_or_fetch_herb_svg)(powiat_id, powiat_name)
            _, metadata = read_heraldry_cache(cache_file)
        except (HTTPException, OSError, ValueError, KeyError, TypeError):
            return None

    attr = metadata["attribution"]
    return PowiatHeraldrySourceAttribution(
        title=attr.get("title"),
        artist=attr.get("artist"),
        author=attr.get("author"),
        license=attr.get("license"),
        source_url=attr.get("source_url"),
        description=" ".join(
            filter(
                None,
                [
                    attr.get("description"),
                    "The display preview, when available, is rasterized and resized from the credited image.",
                ],
            )
        ),
    )


def asset_url(mode: str, target_id: int, token: str, scope: str = "county") -> str:
    if scope != "county":
        return f"/regional-symbols/{scope}/{mode}/session-asset?token={token}"
    if mode == "flag":
        return f"/powiatdle/flags/flag-asset?token={token}"
    return f"/powiatdle/heraldry/coat-asset?token={token}"


def flag_asset_url(county_id: int, record: dict) -> str:
    url = f"/powiatdle/flags/assets/{county_id}"
    version = record["source"].get("asset_sha1") or record["source"].get("sha1")
    return f"{url}?v={urllib.parse.quote(str(version), safe='')}" if version else url


def regional_asset_url(scope: str, mode: str, entity_id: int, record: dict) -> str:
    url = f"/regional-symbols/{scope}/{mode}/assets/{entity_id}"
    version = record["source"].get("asset_sha1") or record["source"].get("sha1")
    return f"{url}?v={urllib.parse.quote(str(version), safe='')}" if version else url


@lru_cache(maxsize=16)
def thumbnail_manifest(directory: Path, mode: str) -> dict:
    try:
        data = json.loads((directory / f"{mode}-manifest.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def thumbnail_entry(directory: Path, mode: str, entity_id: int, record: dict) -> Optional[dict]:
    entry = thumbnail_manifest(directory, mode).get(str(entity_id))
    version = record["source"].get("asset_sha1") or record["source"].get("sha1")
    if (
        not isinstance(entry, dict)
        or entry.get("source_sha1") != version
        or not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("sha256", "")))
        or entry.get("filename") != f"{mode}-{entity_id}.webp"
    ):
        return None
    return entry


def thumbnail_url(
    directory: Path, mode: str, entity_id: int, record: dict, base: str, fallback: str
) -> str:
    entry = thumbnail_entry(directory, mode, entity_id, record)
    return f"{base}/thumbnails/{entity_id}?v={entry['sha256']}" if entry else fallback


async def thumbnail_response(
    directory: Path, mode: str, entity_id: int, record: dict, version: str
) -> Response:
    entry = thumbnail_entry(directory, mode, entity_id, record)
    if not entry or version != entry["sha256"]:
        raise HTTPException(status_code=404, detail="Thumbnail version not found.")
    try:
        data = await asyncio.to_thread((directory / entry["filename"]).read_bytes)
    except OSError:
        raise HTTPException(status_code=503, detail="Thumbnail unavailable.")
    return Response(
        content=data,
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


def thumbnail_credit(source, has_thumbnail: bool):
    if not has_thumbnail:
        return source
    note = "Quiz thumbnail rasterized and resized from the credited image."
    return source.model_copy(
        update={"description": " ".join(filter(None, [source.description, note]))}
    )


def source_attribution(mode: str, target: dict, scope: str = "county"):
    if scope != "county" or mode == "flag":
        record = (
            regional_catalog.load_catalog(scope, mode)[target["id"]]
            if scope != "county"
            else flag_catalog.load_catalog()[target["id"]]
        )
        source = record["source"]
        directory = (
            regional_catalog.DATA_ROOT / scope / "previews"
            if scope != "county"
            else flag_catalog.ASSET_DIR.parent / "flag_previews"
        )
        modification = source.get("modification")
        if thumbnail_entry(directory, mode, target["id"], record):
            modification = " ".join(
                filter(
                    None,
                    [
                        modification,
                        "Display preview rasterized and resized from the credited image.",
                    ],
                )
            )
        fields = dict(
            title=source.get("filename"),
            author=source.get("attribution"),
            license=source.get("license"),
            license_url=source.get("license_url"),
            source_url=source.get("url"),
            description=modification,
        )
        if scope != "county":
            return RegionalSourceAttribution(
                **fields,
                context=source.get("notes"),
                component_credits=source.get("component_credits", []),
            )
        return PowiatHeraldrySourceAttribution(**fields)
    return facade_attr("get_source_attribution", get_source_attribution)(
        target["id"], target["name"]
    )


def accepts_gzip(accept_encoding: str) -> bool:
    encodings = {}
    for item in accept_encoding.split(","):
        name, *params = item.split(";")
        name = name.strip().lower()
        if name not in ("gzip", "*"):
            continue
        quality = 1.0
        for param in params:
            key, sep, value = param.strip().partition("=")
            if sep and key.strip().lower() == "q":
                try:
                    quality = float(value.strip())
                except ValueError:
                    quality = 0.0
        encodings[name] = min(encodings.get(name, 1.0), quality)
    return encodings.get("gzip", encodings.get("*", 0)) > 0


@lru_cache(maxsize=32)
def compressed_regional_asset(path: Path, version: str) -> bytes:
    return gzip.compress(path.read_bytes(), compresslevel=3, mtime=0)


def reconstruct_guesses(
    payload: dict,
    target: dict,
    scope: str,
    mode: str,
    ranked_row,
) -> list:
    from powiatdle.heraldry_pkg.catalog import (
        bearing_between,
        distance_between,
        entity_by_id,
        get_registration_plates,
    )
    from powiatdle.heraldry_pkg.schemas import (
        PowiatHeraldryGuessResult,
        PowiatHeraldryTarget,
        encrypt_session_token,
    )

    guesses_ids = payload.get("guesses", [])
    plates_fn = facade_attr("get_registration_plates", get_registration_plates)
    reconstructed: list[PowiatHeraldryGuessResult] = []
    for idx, gid in enumerate(guesses_ids):
        g_county = entity_by_id(scope, gid)
        if not g_county:
            continue
        g_made = idx + 1
        g_rem = max(0, 8 - g_made)
        g_correct = gid == target["id"]
        g_won = g_correct
        g_over = g_won or (g_made >= 8)
        g_same_voivodeship = (
            scope == "county"
            and g_county["voivodeship"].strip().lower() == target["voivodeship"].strip().lower()
        )
        if g_correct:
            g_dist, g_deg, g_dir, g_arr = 0, None, None, None
        else:
            g_dist = distance_between(scope, g_county, target)
            g_deg, g_dir, g_arr = bearing_between(scope, g_county, target)

        wrong_so_far = [x for x in guesses_ids[:g_made] if x != target["id"]]
        g_plates = (
            plates_fn(target["id"])
            if scope == "county" and ((not g_correct and len(wrong_so_far) >= 5) or g_over)
            else None
        )
        g_target_obj = (
            PowiatHeraldryTarget(
                id=target["id"], name=target["name"], voivodeship=target["voivodeship"]
            )
            if g_over
            else None
        )
        g_attr = source_attribution(mode, target, scope) if g_over else None
        partial_token = encrypt_session_token(
            {
                "seed": payload["seed"],
                "is_daily": payload["is_daily"],
                "date": payload["date"],
                "target_id": target["id"],
                "symbol_mode": mode,
                **({"entity_scope": scope} if scope != "county" else {}),
                "guesses": guesses_ids[:g_made],
            }
        )
        reconstructed.append(
            PowiatHeraldryGuessResult(
                answer=g_correct,
                guess=g_county["name"],
                powiat_id=g_county["id"],
                voivodeship=g_county["voivodeship"],
                distance_km=g_dist,
                bearing_degrees=g_deg,
                bearing_direction=g_dir,
                bearing_arrow=g_arr,
                same_voivodeship=g_same_voivodeship,
                guesses_made=g_made,
                remaining_guesses=g_rem,
                is_game_over=g_over,
                won=g_won,
                registration_plates=g_plates,
                target_powiat=g_target_obj,
                source_attribution=g_attr,
                ranked=ranked_row is not None,
                points=ranked_row.points if ranked_row is not None and g_over else None,
                token=partial_token,
            )
        )
    return reconstructed
