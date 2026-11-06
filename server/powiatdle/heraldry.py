import asyncio
import base64
import gzip
import hashlib
import io
import json
import logging
import os
import mimetypes
import math
import re
import sqlite3
import threading
import urllib.parse
import urllib.request
import uuid
from functools import lru_cache
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models.user import User
from powiat_names import resolve_powiat_name
from powiatdle.utils import LOCAL_CONFIG
from powiatdle import heraldry_daily
from powiatdle import flag_catalog
from regional_symbols import catalog as regional_catalog
from powiatdle.heraldry_quiz import router as quiz_router
from users.utils import get_current_or_guest_user, get_current_user
from utils.geo import calculate_bearing, calculate_distance_km

logger = logging.getLogger("countrydle.powiatdle.heraldry")

router = APIRouter(prefix="/heraldry", tags=["powiat-heraldry"])
router.include_router(quiz_router)
flag_router = APIRouter(prefix="/flags", tags=["powiat-flags"])
regional_router = APIRouter(prefix="/regional-symbols/{scope}/{mode}", tags=["regional-symbols"])

USER_AGENT = "CountrydleHeraldryBot/1.0 (https://countrydle.com; heraldry@countrydle.com)"
HERB_CACHE_DIR = LOCAL_CONFIG.db_path.parent / "powiat_herb_cache"

PL_ALPHABET = "aąbcćdeęfghijklłmnńoóprsśtuwyzźż"
PL_ORDER = {ch: idx for idx, ch in enumerate(PL_ALPHABET)}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class PowiatHeraldrySourceAttribution(BaseModel):
    title: Optional[str] = None
    artist: Optional[str] = None
    author: Optional[str] = None
    license: Optional[str] = None
    license_url: Optional[str] = None
    source_url: Optional[str] = None
    description: Optional[str] = None


class RegionalComponentCredit(BaseModel):
    title: str
    url: str
    author: str
    license: str
    license_url: Optional[str] = None


class RegionalSourceAttribution(PowiatHeraldrySourceAttribution):
    context: Optional[str] = None
    component_credits: List[RegionalComponentCredit] = Field(default_factory=list)


class PowiatHeraldryTarget(BaseModel):
    id: int
    name: str
    voivodeship: str


class PowiatHeraldryItem(BaseModel):
    id: int
    name: str
    voivodeship: str
    is_city_county: bool


class RegionalSymbolItem(PowiatHeraldryItem):
    aliases: List[str] = Field(default_factory=list)


class PowiatHeraldryGuessRequest(BaseModel):
    token: str
    guess: str
    powiat_id: Optional[int] = None


class PowiatHeraldryGuessResult(BaseModel):
    answer: bool
    guess: str
    powiat_id: int
    voivodeship: str
    distance_km: Optional[int | float] = None
    bearing_degrees: Optional[int] = None
    bearing_direction: Optional[str] = None
    bearing_arrow: Optional[str] = None
    same_voivodeship: bool
    guesses_made: int
    remaining_guesses: int
    is_game_over: bool
    won: bool
    registration_plates: Optional[List[str]] = None
    target_powiat: Optional[PowiatHeraldryTarget] = None
    source_attribution: Optional[RegionalSourceAttribution | PowiatHeraldrySourceAttribution] = None
    token: Optional[str] = None
    ranked: bool = False
    points: Optional[int] = None


class PowiatHeraldryChallenge(BaseModel):
    seed: str
    is_daily: bool
    date: str
    max_guesses: int = 8
    hint_unlock_guesses: int = 5
    token: str
    coat_asset_url: str
    source_attribution: Optional[RegionalSourceAttribution | PowiatHeraldrySourceAttribution] = None
    guesses: Optional[List[PowiatHeraldryGuessResult]] = None
    is_game_over: Optional[bool] = False
    won: Optional[bool] = False
    registration_plates: Optional[List[str]] = None
    target_powiat: Optional[PowiatHeraldryTarget] = None
    ranked: bool = False
    points: Optional[int] = None


# ---------------------------------------------------------------------------
# Security & Crypto
# ---------------------------------------------------------------------------


def get_fernet() -> Fernet:
    secret_key = os.getenv("SECRET_KEY", "fallback_countrydle_secret")
    fernet_key = base64.urlsafe_b64encode(hashlib.sha256(secret_key.encode("utf-8")).digest())
    return Fernet(fernet_key)


def encrypt_session_token(payload: dict) -> str:
    f = get_fernet()
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return f.encrypt(data).decode("utf-8")


def decrypt_session_token(token: str) -> dict:
    if not token or not isinstance(token, str):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing or invalid session token.",
        )
    f = get_fernet()
    try:
        data = f.decrypt(token.encode("utf-8"))
        return json.loads(data.decode("utf-8"))
    except (InvalidToken, Exception) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired heraldry session token.",
        ) from exc


# ---------------------------------------------------------------------------
# Database & Cache Helpers
# ---------------------------------------------------------------------------


def get_db_path() -> Path:
    db_path = getattr(LOCAL_CONFIG, "db_path", None)
    if db_path and Path(db_path).exists():
        return Path(db_path)
    for candidate in [
        Path("data/powiat_facts.sqlite"),
        Path("server/data/powiat_facts.sqlite"),
        Path(__file__).resolve().parent.parent / "data" / "powiat_facts.sqlite",
        Path(__file__).resolve().parent.parent.parent / "data" / "powiat_facts.sqlite",
    ]:
        if candidate.exists():
            return candidate
    return Path(db_path) if db_path else Path("data/powiat_facts.sqlite")


def get_herb_cache_dir() -> Path:
    db_p = get_db_path()
    cache_dir = db_p.parent / "powiat_herb_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir



_HERALDRY_MAP_CACHE: Optional[dict[str, str]] = None


def get_heraldry_filename(powiat_id: int) -> Optional[str]:
    global _HERALDRY_MAP_CACHE
    if _HERALDRY_MAP_CACHE is None:
        map_path = get_db_path().parent / "powiat_heraldry_map.json"
        if not map_path.exists():
            map_path = Path(__file__).with_name("heraldry_map.json")
        if map_path.exists():
            try:
                _HERALDRY_MAP_CACHE = json.loads(map_path.read_text(encoding="utf-8"))
            except Exception:
                _HERALDRY_MAP_CACHE = {}
        else:
            _HERALDRY_MAP_CACHE = {}
    return _HERALDRY_MAP_CACHE.get(str(powiat_id))

def heraldry_cache_path(cache_dir: Path, powiat_id: int) -> Path:
    # Legacy SVGs may have lost their original dimensions.
    return cache_dir / f"{powiat_id}.v2.json"


def _svg_absolute_length(value: str) -> Optional[float]:
    match = re.fullmatch(
        r"\s*([+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*(px|in|cm|mm|q|pt|pc)?\s*",
        value,
        re.IGNORECASE,
    )
    if not match:
        return None
    factors = {"": 1, "px": 1, "in": 96, "cm": 96 / 2.54,
               "mm": 96 / 25.4, "q": 96 / 101.6, "pt": 96 / 72, "pc": 16}
    length = float(match.group(1)) * factors[(match.group(2) or "").lower()]
    return length if 0 < length < float("inf") else None


def sanitize_svg_bytes(content: bytes) -> bytes:
    """Ensure SVG contains xmlns, valid viewBox, and UTF-8 encoding so browsers render it cleanly."""
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = content.decode("iso-8859-1")
        except UnicodeDecodeError:
            text = content.decode("latin1", errors="replace")

    text = re.sub(
        r'<\?xml[^>]*encoding=["\'][^"\']*["\'][^>]*\?>',
        '<?xml version="1.0" encoding="UTF-8"?>',
        text,
        count=1,
    )

    m = re.search(r'<svg([^>]*)>', text)
    if not m:
        return text.encode("utf-8")

    attrs = m.group(1)

    # CSS absolute units must be converted to CSS pixels before creating a
    # user-space viewBox. Percentages and other relative units are not sizes.
    vb_m = re.search(r'\bviewBox\s*=\s*["\']([^"\']+)["\']', attrs, re.IGNORECASE)
    if vb_m:
        viewbox = vb_m.group(1)
    else:
        w_m = re.search(r'(?:^|\s)width\s*=\s*["\']([^"\']+)["\']', attrs)
        h_m = re.search(r'(?:^|\s)height\s*=\s*["\']([^"\']+)["\']', attrs)
        width = _svg_absolute_length(w_m.group(1)) if w_m else None
        height = _svg_absolute_length(h_m.group(1)) if h_m else None
        viewbox = f"0 0 {width:.15g} {height:.15g}" if width is not None and height is not None else None

    stripped_attrs = r'(?:viewBox|xmlns)' if viewbox is None else r'(?:width|height|viewBox|xmlns)'
    clean_attrs = re.sub(rf'\s+{stripped_attrs}\s*=\s*["\'][^"\']*["\']', '', attrs, flags=re.IGNORECASE).strip()

    new_attrs = 'xmlns="http://www.w3.org/2000/svg"'
    if viewbox:
        new_attrs += f' viewBox="{viewbox}"'
    if clean_attrs:
        new_attrs += f' {clean_attrs}'

    new_svg_tag = f'<svg {new_attrs}>'
    text = text[:m.start()] + new_svg_tag + text[m.end():]
    return text.encode("utf-8")

def polish_sort_key(s: str) -> list[int]:
    return [PL_ORDER.get(ch, 1000 + ord(ch)) for ch in s.lower()]


def clean_html(text: Optional[str]) -> Optional[str]:
    if not text:
        return text
    clean = re.sub(r"<[^>]+>", "", text).strip()
    return clean or None


def atomic_write(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.parent / f".tmp_{path.name}_{uuid.uuid4().hex}"
    try:
        if isinstance(data, bytes):
            with open(temp_path, "wb") as f:
                f.write(data)
        else:
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(data)
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass

def read_heraldry_cache(path: Path) -> tuple[bytes, dict]:
    entry = json.loads(path.read_text(encoding="utf-8"))
    svg, metadata = entry["svg"], entry["metadata"]
    if not isinstance(svg, str) or "<svg" not in svg or not isinstance(metadata, dict):
        raise ValueError("Invalid heraldry cache entry")
    if not isinstance(metadata.get("attribution"), dict):
        raise ValueError("Missing heraldry attribution")
    return svg.encode("utf-8"), metadata


def write_heraldry_cache(path: Path, svg: bytes, metadata: dict) -> None:
    entry = {"svg": svg.decode("utf-8"), "metadata": metadata}
    atomic_write(path, json.dumps(entry, ensure_ascii=False))


def get_all_counties(db_path: Optional[Path] = None) -> list[dict]:
    p = db_path or get_db_path()
    with sqlite3.connect(p) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, voivodeship, is_city_county, latitude, longitude "
            "FROM powiats ORDER BY id ASC"
        )
        return [
            {
                "id": int(row["id"]),
                "name": str(row["name"]),
                "voivodeship": str(row["voivodeship"]),
                "is_city_county": bool(row["is_city_county"]),
                "latitude": float(row["latitude"]) if row["latitude"] is not None else 0.0,
                "longitude": float(row["longitude"]) if row["longitude"] is not None else 0.0,
            }
            for row in cur.fetchall()
        ]


def get_county_by_id(county_id: int, db_path: Optional[Path] = None) -> Optional[dict]:
    p = db_path or get_db_path()
    with sqlite3.connect(p) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, voivodeship, is_city_county, latitude, longitude "
            "FROM powiats WHERE id = ? LIMIT 1",
            (county_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": int(row["id"]),
            "name": str(row["name"]),
            "voivodeship": str(row["voivodeship"]),
            "is_city_county": bool(row["is_city_county"]),
            "latitude": float(row["latitude"]) if row["latitude"] is not None else 0.0,
            "longitude": float(row["longitude"]) if row["longitude"] is not None else 0.0,
        }


def get_registration_plates(county_id: int, db_path: Optional[Path] = None) -> list[str]:
    p = db_path or get_db_path()
    with sqlite3.connect(p) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT plate_code FROM powiat_registration_plates WHERE powiat_id = ? ORDER BY plate_code ASC",
            (county_id,),
        )
        return [r[0] for r in cur.fetchall()]


def resolve_guessed_county(
    guess: str, powiat_id: Optional[int] = None, db_path: Optional[Path] = None
) -> Optional[dict]:
    p = db_path or get_db_path()
    if powiat_id is not None:
        c = get_county_by_id(powiat_id, db_path=p)
        if c:
            return c

    clean_guess = guess.strip()
    if not clean_guess:
        return None

    with sqlite3.connect(p) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, voivodeship, is_city_county, latitude, longitude "
            "FROM powiats WHERE LOWER(name) = LOWER(?) LIMIT 1",
            (clean_guess,),
        )
        row = cur.fetchone()
        if row:
            return {
                "id": int(row["id"]),
                "name": str(row["name"]),
                "voivodeship": str(row["voivodeship"]),
                "is_city_county": bool(row["is_city_county"]),
                "latitude": float(row["latitude"]) if row["latitude"] is not None else 0.0,
                "longitude": float(row["longitude"]) if row["longitude"] is not None else 0.0,
            }

        try:
            canonical_name = resolve_powiat_name(conn, clean_guess)
            if canonical_name:
                cur.execute(
                    "SELECT id, name, voivodeship, is_city_county, latitude, longitude "
                    "FROM powiats WHERE LOWER(name) = LOWER(?) LIMIT 1",
                    (canonical_name,),
                )
                row = cur.fetchone()
                if row:
                    return {
                        "id": int(row["id"]),
                        "name": str(row["name"]),
                        "voivodeship": str(row["voivodeship"]),
                        "is_city_county": bool(row["is_city_county"]),
                        "latitude": float(row["latitude"]) if row["latitude"] is not None else 0.0,
                        "longitude": float(row["longitude"]) if row["longitude"] is not None else 0.0,
                    }
        except Exception:
            pass

    return None


# ---------------------------------------------------------------------------
# Wikipedia / Wikidata / Wikimedia Commons Fetcher
# ---------------------------------------------------------------------------


def fetch_url(
    url: str,
    user_agent: str = USER_AGENT,
    max_redirects: int = 5,
    timeout: float = 15.0,
) -> bytes:
    current_url = url
    for _ in range(max_redirects):
        req = urllib.request.Request(current_url, headers={"User-Agent": user_agent})

        class StopRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(StopRedirect)
        try:
            with opener.open(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                location = e.headers.get("Location")
                if not location:
                    raise
                current_url = urllib.parse.urljoin(current_url, location)
                continue
            raise
    raise RuntimeError("Too many redirects")


def _extract_wiki_fallback_coat_filename(wiki_title: str, page: dict) -> Optional[str]:
    images = [
        str(im.get("title", "")).replace("Plik:", "").replace("File:", "").strip()
        for im in page.get("images", [])
        if im.get("title")
    ]
    svg_coa = [img for img in images if img.lower().endswith("coa.svg")]
    if not svg_coa:
        return None
    expected_exact = f"pol {wiki_title.lower()} coa.svg"
    for img in svg_coa:
        if img.lower() == expected_exact:
            return img
    if wiki_title.lower().startswith("powiat "):
        for img in svg_coa:
            if img.lower().startswith("pol powiat "):
                return img
    return svg_coa[0]


def resolve_and_fetch_heraldry(wiki_title: str, filename: Optional[str] = None) -> tuple[bytes, dict]:
    if not filename:
        wiki_url = (
            f"https://pl.wikipedia.org/w/api.php?action=query"
            f"&titles={urllib.parse.quote(wiki_title)}&prop=pageprops|images&imlimit=50&redirects=1&format=json"
        )
        wiki_data = json.loads(fetch_url(wiki_url).decode("utf-8"))
        pages = wiki_data.get("query", {}).get("pages", {})
        if not pages:
            raise ValueError(f"No Wikipedia page found for '{wiki_title}'")
        page = next(iter(pages.values()))
        qid = page.get("pageprops", {}).get("wikibase_item")
        if qid:
            wd_url = f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={qid}&props=claims&format=json"
            wd_data = json.loads(fetch_url(wd_url).decode("utf-8"))
            claims = wd_data.get("entities", {}).get(qid, {}).get("claims", {})
            p94 = claims.get("P94")
            if p94:
                filename = p94[0].get("mainsnak", {}).get("datavalue", {}).get("value")
        if not filename:
            filename = _extract_wiki_fallback_coat_filename(wiki_title, page)
        if not filename:
            raise ValueError(f"No coat of arms filename found on Wikidata ({qid}) or Wikipedia for '{wiki_title}'")
    # 3. commons metadata
    commons_title = f"File:{filename}"
    commons_url = (
        f"https://commons.wikimedia.org/w/api.php?action=query"
        f"&titles={urllib.parse.quote(commons_title)}&prop=imageinfo&iiprop=url|extmetadata&format=json"
    )
    c_bytes = fetch_url(commons_url)
    c_data = json.loads(c_bytes.decode("utf-8"))
    c_pages = c_data.get("query", {}).get("pages", {})
    c_page = next(iter(c_pages.values()))
    imageinfo = c_page.get("imageinfo", [{}])[0]
    file_url = imageinfo.get("url")
    extmeta = imageinfo.get("extmetadata", {})

    attr = {
        "title": filename,
        "artist": clean_html(extmeta.get("Artist", {}).get("value")),
        "author": clean_html(
            extmeta.get("Artist", {}).get("value") or extmeta.get("Credit", {}).get("value")
        ),
        "license": extmeta.get("LicenseShortName", {}).get("value")
        or extmeta.get("UsageTerms", {}).get("value"),
        "source_url": imageinfo.get("descriptionurl")
        or f"https://commons.wikimedia.org/wiki/File:{urllib.parse.quote(filename)}",
        "description": clean_html(extmeta.get("ImageDescription", {}).get("value")),
    }

    # 4. download SVG bytes
    svg_download_url = (
        file_url
        or f"https://commons.wikimedia.org/wiki/Special:FilePath/{urllib.parse.quote(filename)}"
    )
    svg_bytes = sanitize_svg_bytes(fetch_url(svg_download_url))
    if not svg_bytes or (b"<svg" not in svg_bytes and b"<?xml" not in svg_bytes):
        raise ValueError(f"Downloaded file for '{filename}' is not valid SVG content")

    meta = {
        "filename": filename,
        "url": file_url or svg_download_url,
        "attribution": attr,
    }
    return svg_bytes, meta


def get_or_fetch_herb_svg(powiat_id: int, powiat_name: str) -> bytes:
    cache_file = heraldry_cache_path(get_herb_cache_dir(), powiat_id)
    try:
        return read_heraldry_cache(cache_file)[0]
    except (OSError, ValueError, KeyError, TypeError):
        pass

    try:
        svg_bytes, meta = resolve_and_fetch_heraldry(powiat_name, get_heraldry_filename(powiat_id))
        write_heraldry_cache(cache_file, svg_bytes, meta)
        return svg_bytes
    except Exception as exc:
        try:
            return read_heraldry_cache(cache_file)[0]
        except (OSError, ValueError, KeyError, TypeError):
            pass
        logger.warning(
            f"Failed to fetch coat of arms for powiat {powiat_id} ({powiat_name}): {exc}"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Coat of arms asset temporarily unavailable.",
        ) from exc


def get_or_fetch_herb_thumb(
    powiat_id: int, powiat_name: str, width: int = 80
) -> tuple[bytes, str]:
    """Return a source-bound PNG thumbnail or the original SVG."""
    root = get_herb_cache_dir()
    cached_svg = None
    try:
        cached_svg, metadata = read_heraldry_cache(heraldry_cache_path(root, powiat_id))
        filename = metadata.get("filename")
    except (OSError, ValueError, KeyError, TypeError):
        filename = None
    filename = filename or get_heraldry_filename(powiat_id)
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
            png_bytes = fetch_url(thumb_url)
            if png_bytes.startswith(b"\x89PNG\r\n\x1a\n") and len(png_bytes) >= 64:
                atomic_write(thumb_file, png_bytes)
                return png_bytes, "image/png"
        except Exception as exc:
            logger.warning("Thumbnail fetch failed for powiat %s (%s): %s", powiat_id, filename, exc)
    if cached_svg is not None:
        return cached_svg, "image/svg+xml"
    return get_or_fetch_herb_svg(powiat_id, powiat_name), "image/svg+xml"

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
        root = get_herb_cache_dir()
        cache_file = heraldry_cache_path(root, powiat_id)
        try:
            stat = cache_file.stat()
            identity = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
            filename = cached_heraldry_source(cache_file, identity)
        except (OSError, ValueError, KeyError, TypeError):
            filename = None
        filename = filename or get_heraldry_filename(powiat_id)
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
                source = fetch_url(url)
                with Image.open(io.BytesIO(source)) as image:
                    if image.format != "PNG":
                        raise ValueError("Thumbnail source is not PNG")
                    image.thumbnail((512, 512), Image.Resampling.LANCZOS)
                    output = io.BytesIO()
                    image.save(output, format="WEBP", quality=85, method=4, exact=True)
                data = output.getvalue()
                atomic_write(path, data)
                return data, "image/webp"
            except (OSError, ValueError, RuntimeError) as exc:
                logger.warning("Daily thumbnail unavailable for powiat %s: %s", powiat_id, exc)
        return get_or_fetch_herb_svg(powiat_id, powiat_name), "image/svg+xml"


def get_source_attribution(
    powiat_id: int, powiat_name: Optional[str] = None
) -> Optional[PowiatHeraldrySourceAttribution]:
    cache_file = heraldry_cache_path(get_herb_cache_dir(), powiat_id)
    try:
        _, metadata = read_heraldry_cache(cache_file)
    except (OSError, ValueError, KeyError, TypeError):
        if not powiat_name:
            return None
        try:
            get_or_fetch_herb_svg(powiat_id, powiat_name)
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
        description=" ".join(filter(None, [attr.get("description"),
            "The display preview, when available, is rasterized and resized from the credited image."])),
    )


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

def symbol_mode(request: Request) -> str:
    return request.path_params.get("mode") or ("flag" if "/flags/" in request.url.path else "coat")


def entity_scope(request: Request) -> str:
    scope = request.path_params.get("scope", "county")
    if scope != "county" and scope not in regional_catalog.SCOPES:
        raise HTTPException(status_code=404, detail="Unknown geography.")
    if scope == "county" and "scope" in request.path_params:
        raise HTTPException(status_code=404, detail="Unknown geography.")
    return scope


def entities_for(scope: str) -> list[dict]:
    if scope == "county":
        return get_all_counties()
    return [dict(entity, voivodeship="", is_city_county=False)
            for entity in regional_catalog.load_entities(scope).values()]


def entity_by_id(scope: str, entity_id: int) -> Optional[dict]:
    if scope == "county":
        return get_county_by_id(entity_id)
    entity = regional_catalog.load_entities(scope).get(entity_id)
    return dict(entity, voivodeship="", is_city_county=False) if entity else None


def resolve_entity(scope: str, guess: str, entity_id: Optional[int]) -> Optional[dict]:
    if scope == "county":
        return resolve_guessed_county(guess, entity_id)
    if entity_id is not None:
        return entity_by_id(scope, entity_id)
    key = regional_catalog.normalize(guess)
    for entity in entities_for(scope):
        if key and key in {regional_catalog.normalize(form) for form in [entity["name"], *entity["aliases"]]}:
            return entity
    return None


def regional_target(scope: str, mode: str, seed: str) -> dict:
    records = regional_catalog.load_catalog(scope, mode)
    ids = regional_catalog.load_daily_ids(scope, mode) if seed.startswith("daily-") else sorted(records)
    value = int(hashlib.sha256(f"regional-symbols:{scope}:{mode}:{seed}".encode()).hexdigest(), 16)
    return entity_by_id(scope, ids[value % len(ids)])


def distance_between(scope: str, source: dict, target: dict) -> float:
    if scope == "county":
        return calculate_distance_km(source["latitude"], source["longitude"], target["latitude"], target["longitude"])
    lat1, lat2 = math.radians(source["latitude"]), math.radians(target["latitude"])
    dlat = lat2 - lat1
    dlon = math.radians(target["longitude"] - source["longitude"])
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return round(12742 * math.asin(min(1, math.sqrt(a))), 2)


def bearing_between(scope: str, source: dict, target: dict):
    if (scope != "county" and source["latitude"] == target["latitude"]
            and source["longitude"] == target["longitude"]):
        return None, None, None
    return calculate_bearing(source["latitude"], source["longitude"], target["latitude"], target["longitude"])


def require_token_scope(payload: dict, scope: str):
    if payload.get("entity_scope", "county") != scope:
        raise HTTPException(status_code=403, detail="Token belongs to another geography.")


def select_target(counties: list[dict], seed: str, symbol_mode: str = "coat") -> dict:
    if symbol_mode == "flag":
        catalog = flag_catalog.load_catalog()
        if seed.startswith("daily-"):
            ids = flag_catalog.load_daily_ids()
            by_id = {county["id"]: county for county in counties}
            if any(county_id not in catalog or county_id not in by_id for county_id in ids):
                raise HTTPException(status_code=503, detail="Flag daily pool unavailable.")
            counties = [by_id[county_id] for county_id in ids]
        else:
            counties = [county for county in counties if county["id"] in catalog]
    if not counties:
        raise HTTPException(status_code=503, detail="No counties catalog available.")
    namespace = "powiat-flags" if symbol_mode == "flag" else "powiat-heraldry"
    value = int(hashlib.sha256(f"{namespace}:{seed}".encode("utf-8")).hexdigest(), 16)
    return counties[value % len(counties)]


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
    if (not isinstance(entry, dict) or entry.get("source_sha1") != version
            or not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("sha256", "")))
            or entry.get("filename") != f"{mode}-{entity_id}.webp"):
        return None
    return entry


def thumbnail_url(directory: Path, mode: str, entity_id: int, record: dict, base: str, fallback: str) -> str:
    entry = thumbnail_entry(directory, mode, entity_id, record)
    return f"{base}/thumbnails/{entity_id}?v={entry['sha256']}" if entry else fallback


async def thumbnail_response(directory: Path, mode: str, entity_id: int, record: dict, version: str) -> Response:
    entry = thumbnail_entry(directory, mode, entity_id, record)
    if not entry or version != entry["sha256"]:
        raise HTTPException(status_code=404, detail="Thumbnail version not found.")
    try:
        data = await asyncio.to_thread((directory / entry["filename"]).read_bytes)
    except OSError:
        raise HTTPException(status_code=503, detail="Thumbnail unavailable.")
    return Response(content=data, media_type="image/webp",
                    headers={"Cache-Control": "public, max-age=31536000, immutable"})


def thumbnail_credit(source, has_thumbnail: bool):
    if not has_thumbnail:
        return source
    note = "Quiz thumbnail rasterized and resized from the credited image."
    return source.model_copy(update={"description": " ".join(filter(None, [source.description, note]))})


def source_attribution(mode: str, target: dict, scope: str = "county"):
    if scope != "county" or mode == "flag":
        record = (regional_catalog.load_catalog(scope, mode)[target["id"]]
                  if scope != "county" else flag_catalog.load_catalog()[target["id"]])
        source = record["source"]
        directory = (regional_catalog.DATA_ROOT / scope / "previews" if scope != "county"
                     else flag_catalog.ASSET_DIR.parent / "flag_previews")
        modification = source.get("modification")
        if thumbnail_entry(directory, mode, target["id"], record):
            modification = " ".join(filter(None, [modification,
                "Display preview rasterized and resized from the credited image."]))
        fields = dict(title=source.get("filename"), author=source.get("attribution"),
                      license=source.get("license"), license_url=source.get("license_url"),
                      source_url=source.get("url"), description=modification)
        if scope != "county":
            return RegionalSourceAttribution(**fields, context=source.get("notes"),
                                             component_credits=source.get("component_credits", []))
        return PowiatHeraldrySourceAttribution(**fields)
    return get_source_attribution(target["id"], target["name"])


def require_token_mode(payload: dict, mode: str):
    if payload.get("symbol_mode", "coat") != mode:
        raise HTTPException(status_code=403, detail="Token belongs to another symbol mode.")



@router.get("/counties", response_model=List[PowiatHeraldryItem])
async def get_counties():
    """Returns catalog of all counties sorted alphabetically by name."""
    counties = get_all_counties()
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
    return [RegionalSymbolItem(id=e["id"], name=e["name"], aliases=e["aliases"],
                              voivodeship="", is_city_county=False)
            for e in sorted(entities_for(scope), key=lambda entity: entity["name"].casefold())]


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

    target_county = (select_target(all_counties, effective_seed, mode) if scope == "county"
                     else regional_target(scope, mode, effective_seed))
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
    if is_daily and parsed_token and parsed_token.get("session_id") and parsed_token.get("seed") == effective_seed:
        ranked_row = await heraldry_daily.get_owned_daily(
            session, request, user, parsed_token["session_id"], symbol_mode=mode, entity_scope=scope
        )
        token = encrypt_session_token(heraldry_daily.token_payload(ranked_row))
    elif is_daily and (not parsed_token or parsed_token.get("seed") != effective_seed):
        ranked_row = await heraldry_daily.get_or_create_daily(
            session, request, response, user, datetime.now(timezone.utc).date(), target_county,
            symbol_mode=mode, entity_scope=scope
        )
        token = encrypt_session_token(heraldry_daily.token_payload(ranked_row))

    if token:
        try:
            payload = decrypt_session_token(token)
            if payload.get("seed") == effective_seed:
                payload_target_id = payload.get("target_id", target_id)
                target = entity_by_id(scope, payload_target_id) or target_county
                guesses_ids = payload.get("guesses", [])

                reconstructed_guesses: list[PowiatHeraldryGuessResult] = []
                for idx, gid in enumerate(guesses_ids):
                    g_county = entity_by_id(scope, gid)
                    if not g_county:
                        continue
                    g_made = idx + 1
                    g_rem = max(0, 8 - g_made)
                    g_correct = gid == target["id"]
                    g_won = g_correct
                    g_over = g_won or (g_made >= 8)
                    g_same_voivodeship = (scope == "county" and
                        g_county["voivodeship"].strip().lower() == target["voivodeship"].strip().lower())

                    if g_correct:
                        g_dist = 0
                        g_deg = None
                        g_dir = None
                        g_arr = None
                    else:
                        g_dist = distance_between(scope, g_county, target)
                        g_deg, g_dir, g_arr = bearing_between(scope, g_county, target)

                    wrong_so_far = [x for x in guesses_ids[:g_made] if x != target["id"]]
                    g_plates = None
                    if scope == "county" and ((not g_correct and len(wrong_so_far) >= 5) or g_over):
                        g_plates = get_registration_plates(target["id"])

                    g_target_obj = None
                    g_attr = None
                    if g_over:
                        g_target_obj = PowiatHeraldryTarget(
                            id=target["id"],
                            name=target["name"],
                            voivodeship=target["voivodeship"],
                        )
                        g_attr = source_attribution(mode, target, scope)

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

                    reconstructed_guesses.append(
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

                won = any(gid == target["id"] for gid in guesses_ids)
                is_game_over = won or (len(guesses_ids) >= 8)
                wrong_guesses = [gid for gid in guesses_ids if gid != target["id"]]

                registration_plates = None
                if scope == "county" and (len(wrong_guesses) >= 5 or is_game_over):
                    registration_plates = get_registration_plates(target["id"])

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

    # Fresh session token
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


@router.get("/coat-asset")
async def get_coat_asset(token: str = Query(...), full: bool = Query(False),
                         accept_encoding: str = Header(default="")):
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
    county = get_county_by_id(target_id)
    if not county:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target county not found.",
        )

    if full:
        data = await asyncio.to_thread(get_or_fetch_herb_svg, target_id, county["name"])
        media_type = "image/svg+xml"
    else:
        data, media_type = await asyncio.to_thread(get_daily_herb_preview, target_id, county["name"])
    headers = {"Cache-Control": "private, no-store"}
    if media_type == "image/svg+xml":
        headers["Vary"] = "Accept-Encoding"
        if accepts_gzip(accept_encoding):
            data = await asyncio.to_thread(gzip.compress, data, compresslevel=3, mtime=0)
            headers["Content-Encoding"] = "gzip"
    return Response(content=data, media_type=media_type, headers=headers)


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

    is_already_won = target_id in guesses
    is_already_over = is_already_won or (len(guesses) >= 8)
    if is_already_over:
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
        ranked_row = await heraldry_daily.record_guess(session, request, user, payload, guessed_county,
                                                        symbol_mode=mode, entity_scope=scope)


    guesses.append(guessed_id)
    payload["guesses"] = guesses
    guesses_made = len(guesses)
    remaining_guesses = max(0, 8 - guesses_made)

    is_correct = guessed_id == target_id
    won = is_correct
    is_game_over = won or (guesses_made >= 8)

    same_voivodeship = (scope == "county" and
        guessed_county["voivodeship"].strip().lower() == target_county["voivodeship"].strip().lower())

    if is_correct:
        distance_km = 0
        bearing_degrees = None
        bearing_direction = None
        bearing_arrow = None
    else:
        distance_km = distance_between(scope, guessed_county, target_county)
        deg, direction, arrow = bearing_between(scope, guessed_county, target_county)
        bearing_degrees = deg
        bearing_direction = direction
        bearing_arrow = arrow

    if scope == "county" and ((not is_correct and guesses_made >= 5) or is_game_over):
        registration_plates = get_registration_plates(target_id)
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
    row = await heraldry_daily.claim_daily(session, request, user, symbol_mode=mode, entity_scope=scope)
    token = encrypt_session_token(heraldry_daily.token_payload(row))
    return await get_challenge(request=request, response=response, seed=None, token=token, user=user, session=session)


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


@flag_router.get("/counties", response_model=List[PowiatHeraldryItem])
async def flag_counties():
    flag_catalog.load_catalog()
    return await get_counties()




@flag_router.get("/catalog")
async def flag_county_catalog():
    catalog = flag_catalog.load_catalog()
    counties = [c for c in get_all_counties() if c["id"] in catalog]
    if not counties:
        raise HTTPException(status_code=503, detail="Flag catalog unavailable.")
    counties.sort(key=lambda c: polish_sort_key(c["name"]))
    return [
        {"id": c["id"], "name": c["name"], "voivodeship": c["voivodeship"],
         "is_city_county": c["is_city_county"],
         "flag_asset_url": flag_asset_url(c["id"], catalog[c["id"]]),
         "thumbnail_asset_url": thumbnail_url(flag_catalog.ASSET_DIR.parent / "flag_thumbnails", "flag",
                                              c["id"], catalog[c["id"]], "/powiatdle/flags",
                                              flag_asset_url(c["id"], catalog[c["id"]])),
         "source_attribution": thumbnail_credit(source_attribution("flag", c), bool(thumbnail_entry(
             flag_catalog.ASSET_DIR.parent / "flag_thumbnails", "flag", c["id"], catalog[c["id"]])))}
        for c in counties
    ]


@flag_router.get("/thumbnails/{county_id}")
async def flag_thumbnail(county_id: int, v: str = Query(...)):
    record = flag_catalog.load_catalog().get(county_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Flag not found.")
    return await thumbnail_response(flag_catalog.ASSET_DIR.parent / "flag_thumbnails",
                                    "flag", county_id, record, v)


@flag_router.get("/assets/{county_id}")
async def flag_asset(county_id: int, v: Optional[str] = Query(None), accept_encoding: str = Header(default="")):
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
    headers = {"Cache-Control": "public, max-age=31536000, immutable" if version and v == version else "no-cache"}
    if media_type == "image/svg+xml":
        headers["Vary"] = "Accept-Encoding"
        if accepts_gzip(accept_encoding):
            data = await asyncio.to_thread(gzip.compress, data, compresslevel=3, mtime=0)
            headers["Content-Encoding"] = "gzip"
    return Response(content=data, media_type=media_type, headers=headers)


@flag_router.get("/flag-asset")
async def flag_session_asset(token: str = Query(...), full: bool = Query(False),
                             accept_encoding: str = Header(default="")):
    payload = decrypt_session_token(token)
    require_token_mode(payload, "flag")
    require_token_scope(payload, "county")
    target_id = payload.get("target_id")
    if type(target_id) is not int or target_id not in flag_catalog.load_catalog():
        raise HTTPException(status_code=403, detail="Flag target is not in the catalog.")
    directory = flag_catalog.ASSET_DIR.parent / "flag_previews"
    entry = thumbnail_entry(directory, "flag", target_id, flag_catalog.load_catalog()[target_id])
    if entry and not full:
        try:
            response = await thumbnail_response(directory, "flag", target_id,
                                                flag_catalog.load_catalog()[target_id], entry["sha256"])
        except HTTPException as exc:
            if exc.status_code != 503:
                raise
            response = await flag_asset(target_id, v=None, accept_encoding=accept_encoding)
    else:
        response = await flag_asset(target_id, v=None, accept_encoding=accept_encoding)
    response.headers["Cache-Control"] = "private, no-store"
    return response


def regional_asset_url(scope: str, mode: str, entity_id: int, record: dict) -> str:
    url = f"/regional-symbols/{scope}/{mode}/assets/{entity_id}"
    version = record["source"].get("asset_sha1") or record["source"].get("sha1")
    return f"{url}?v={urllib.parse.quote(str(version), safe='')}" if version else url


@regional_router.get("/catalog")
async def regional_symbol_catalog(request: Request):
    scope, mode = entity_scope(request), symbol_mode(request)
    records = regional_catalog.load_catalog(scope, mode)
    entities = regional_catalog.load_entities(scope)
    return [
        {"id": entity["id"], "name": entity["name"], "aliases": entity["aliases"],
         "voivodeship": "", "is_city_county": False,
         "flag_asset_url": regional_asset_url(scope, mode, entity["id"], records[entity["id"]]),
         "thumbnail_asset_url": thumbnail_url(regional_catalog.DATA_ROOT / scope / "thumbnails", mode,
                                              entity["id"], records[entity["id"]],
                                              f"/regional-symbols/{scope}/{mode}",
                                              regional_asset_url(scope, mode, entity["id"], records[entity["id"]])),
         "source_attribution": thumbnail_credit(source_attribution(mode, entity, scope), bool(thumbnail_entry(
             regional_catalog.DATA_ROOT / scope / "thumbnails", mode, entity["id"], records[entity["id"]])))}
        for entity in sorted((entities[id_] for id_ in records), key=lambda e: e["name"].casefold())
    ]


@regional_router.get("/thumbnails/{entity_id}")
async def regional_thumbnail(request: Request, entity_id: int, v: str = Query(...)):
    scope, mode = entity_scope(request), symbol_mode(request)
    record = regional_catalog.load_catalog(scope, mode).get(entity_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Symbol not found.")
    return await thumbnail_response(regional_catalog.DATA_ROOT / scope / "thumbnails",
                                    mode, entity_id, record, v)


@lru_cache(maxsize=32)
def compressed_regional_asset(path: Path, version: str) -> bytes:
    return gzip.compress(path.read_bytes(), compresslevel=3, mtime=0)


@regional_router.get("/assets/{entity_id}")
async def regional_asset(request: Request, entity_id: int, v: Optional[str] = Query(None),
                         accept_encoding: str = Header(default="")):
    scope, mode = entity_scope(request), symbol_mode(request)
    record = regional_catalog.load_catalog(scope, mode).get(entity_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Symbol not found.")
    version = record["source"].get("asset_sha1") or record["source"].get("sha1")
    if v is not None and v != version:
        raise HTTPException(status_code=404, detail="Symbol version not found.")
    path = regional_catalog.DATA_ROOT / scope / "assets" / record["filename"]
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    headers = {"Cache-Control": "public, max-age=31536000, immutable" if version and v == version else "no-cache"}
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


@regional_router.get("/session-asset")
async def regional_session_asset(request: Request, token: str = Query(...), full: bool = Query(False),
                                 accept_encoding: str = Header(default="")):
    scope, mode = entity_scope(request), symbol_mode(request)
    payload = decrypt_session_token(token)
    require_token_scope(payload, scope)
    require_token_mode(payload, mode)
    target_id = payload.get("target_id")
    if type(target_id) is not int or target_id not in regional_catalog.load_catalog(scope, mode):
        raise HTTPException(status_code=403, detail="Symbol target is not in the catalog.")
    record = regional_catalog.load_catalog(scope, mode)[target_id]
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


regional_router.add_api_route("/challenge", get_challenge, methods=["GET"], response_model=PowiatHeraldryChallenge)
regional_router.add_api_route("/guess", make_guess, methods=["POST"], response_model=PowiatHeraldryGuessResult)
regional_router.add_api_route("/sync", sync_daily, methods=["POST"], response_model=PowiatHeraldryChallenge)
regional_router.add_api_route("/leaderboard", daily_leaderboard, methods=["GET"])


flag_router.add_api_route("/challenge", get_challenge, methods=["GET"], response_model=PowiatHeraldryChallenge)
flag_router.add_api_route("/guess", make_guess, methods=["POST"], response_model=PowiatHeraldryGuessResult)
flag_router.add_api_route("/sync", sync_daily, methods=["POST"], response_model=PowiatHeraldryChallenge)
flag_router.add_api_route("/leaderboard", daily_leaderboard, methods=["GET"])

from powiatdle.heraldry_quiz import flags_quiz_router, regional_quiz_router

flag_router.include_router(flags_quiz_router)
regional_router.include_router(regional_quiz_router)
