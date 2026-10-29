import asyncio
import base64
import hashlib
import json
import logging
import os
import re
import sqlite3
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from powiat_names import resolve_powiat_name
from powiatdle.utils import LOCAL_CONFIG
from utils.geo import calculate_bearing, calculate_distance_km

logger = logging.getLogger("countrydle.powiatdle.heraldry")

router = APIRouter(prefix="/heraldry", tags=["powiat-heraldry"])

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
    source_url: Optional[str] = None
    description: Optional[str] = None


class PowiatHeraldryTarget(BaseModel):
    id: int
    name: str
    voivodeship: str


class PowiatHeraldryItem(BaseModel):
    id: int
    name: str
    voivodeship: str
    is_city_county: bool


class PowiatHeraldryGuessRequest(BaseModel):
    token: str
    guess: str
    powiat_id: Optional[int] = None


class PowiatHeraldryGuessResult(BaseModel):
    answer: bool
    guess: str
    powiat_id: int
    voivodeship: str
    distance_km: Optional[int] = None
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
    source_attribution: Optional[PowiatHeraldrySourceAttribution] = None
    token: Optional[str] = None


class PowiatHeraldryChallenge(BaseModel):
    seed: str
    is_daily: bool
    date: str
    max_guesses: int = 8
    hint_unlock_guesses: int = 5
    token: str
    coat_asset_url: str
    source_attribution: Optional[PowiatHeraldrySourceAttribution] = None
    guesses: Optional[List[PowiatHeraldryGuessResult]] = None
    is_game_over: Optional[bool] = False
    won: Optional[bool] = False
    registration_plates: Optional[List[str]] = None
    target_powiat: Optional[PowiatHeraldryTarget] = None


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
        if map_path.exists():
            try:
                _HERALDRY_MAP_CACHE = json.loads(map_path.read_text(encoding="utf-8"))
            except Exception:
                _HERALDRY_MAP_CACHE = {}
        else:
            _HERALDRY_MAP_CACHE = {}
    return _HERALDRY_MAP_CACHE.get(str(powiat_id))

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

    # Extract existing viewBox or build from width/height
    vb_m = re.search(r'viewBox=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
    if vb_m:
        viewbox = vb_m.group(1)
    else:
        w_m = re.search(r'width=["\']([0-9.]+)(?:px|pt)?["\']', attrs)
        h_m = re.search(r'height=["\']([0-9.]+)(?:px|pt)?["\']', attrs)
        if w_m and h_m:
            viewbox = f"0 0 {w_m.group(1)} {h_m.group(1)}"
        else:
            viewbox = None

    clean_attrs = re.sub(r'\s*(?:width|height|viewBox|viewbox|xmlns)=["\'][^"\']*["\']', '', attrs).strip()

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


def resolve_and_fetch_heraldry(wiki_title: str) -> tuple[bytes, dict]:
    # 1. pl.wikipedia.org -> wikibase_item (QID) + page images fallback
    wiki_url = (
        f"https://pl.wikipedia.org/w/api.php?action=query"
        f"&titles={urllib.parse.quote(wiki_title)}&prop=pageprops|images&imlimit=50&redirects=1&format=json"
    )
    wiki_bytes = fetch_url(wiki_url)
    wiki_data = json.loads(wiki_bytes.decode("utf-8"))
    pages = wiki_data.get("query", {}).get("pages", {})
    if not pages:
        raise ValueError(f"No Wikipedia page found for '{wiki_title}'")
    page = next(iter(pages.values()))
    qid = page.get("pageprops", {}).get("wikibase_item")

    filename: Optional[str] = None
    if qid:
        # 2. wikidata -> P94 (coat of arms filename)
        wd_url = f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={qid}&props=claims&format=json"
        wd_bytes = fetch_url(wd_url)
        wd_data = json.loads(wd_bytes.decode("utf-8"))
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
    cache_dir = get_herb_cache_dir()
    svg_file = cache_dir / f"{powiat_id}.svg"
    json_file = cache_dir / f"{powiat_id}.json"

    if svg_file.exists():
        try:
            return sanitize_svg_bytes(svg_file.read_bytes())
        except Exception:
            pass

    try:
        svg_bytes, meta = resolve_and_fetch_heraldry(powiat_name)
        atomic_write(svg_file, svg_bytes)
        atomic_write(json_file, json.dumps(meta, ensure_ascii=False, indent=2))
        return svg_bytes
    except Exception as exc:
        if svg_file.exists():
            try:
                return svg_file.read_bytes()
            except Exception:
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
    """Return a lightweight low-resolution PNG thumbnail for list views."""
    cache_dir = get_herb_cache_dir() / "thumbs"
    cache_dir.mkdir(parents=True, exist_ok=True)
    thumb_file = cache_dir / f"thumb_{width}_{powiat_id}.png"

    if thumb_file.exists():
        try:
            data = thumb_file.read_bytes()
            if len(data) > 64:
                return data, "image/png"
        except Exception:
            pass

    filename = get_heraldry_filename(powiat_id)
    if not filename:
        json_file = get_herb_cache_dir() / f"{powiat_id}.json"
        if json_file.exists():
            try:
                filename = json.loads(json_file.read_text(encoding="utf-8")).get("filename")
            except Exception:
                filename = None

    if filename:
        thumb_url = (
            f"https://commons.wikimedia.org/wiki/Special:FilePath/"
            f"{urllib.parse.quote(filename)}?width={width}"
        )
        try:
            png_bytes = fetch_url(thumb_url)
            if png_bytes and len(png_bytes) > 64:
                atomic_write(thumb_file, png_bytes)
                return png_bytes, "image/png"
        except Exception as exc:
            logger.warning(
                f"Thumbnail fetch failed for powiat {powiat_id} ({filename}), falling back to SVG: {exc}"
            )

    svg_bytes = get_or_fetch_herb_svg(powiat_id, powiat_name)
    return svg_bytes, "image/svg+xml"


def get_source_attribution(
    powiat_id: int, powiat_name: Optional[str] = None
) -> Optional[PowiatHeraldrySourceAttribution]:
    cache_dir = get_herb_cache_dir()
    json_file = cache_dir / f"{powiat_id}.json"

    if not json_file.exists() and powiat_name:
        try:
            get_or_fetch_herb_svg(powiat_id, powiat_name)
        except Exception:
            pass

    if json_file.exists():
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            attr = data.get("attribution", {})
            return PowiatHeraldrySourceAttribution(
                title=attr.get("title"),
                artist=attr.get("artist"),
                author=attr.get("author"),
                license=attr.get("license"),
                source_url=attr.get("source_url"),
                description=attr.get("description"),
            )
        except Exception:
            return None
    return None


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------


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


@router.get("/challenge", response_model=PowiatHeraldryChallenge)
async def get_challenge(
    seed: Optional[str] = Query(None),
    token: Optional[str] = Query(None),
):
    """Retrieves or restores a heraldry challenge (daily or custom seed)."""
    all_counties = get_all_counties()
    if not all_counties:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No counties catalog available.",
        )

    today_str = datetime.now(timezone.utc).date().isoformat()
    if not seed or seed.strip() == "daily":
        is_daily = True
        effective_seed = f"daily-{today_str}"
    else:
        is_daily = False
        effective_seed = seed.strip()[:64]

    seed_hash_int = int(
        hashlib.sha256(f"powiat-heraldry:{effective_seed}".encode("utf-8")).hexdigest(),
        16,
    )
    target_idx = seed_hash_int % len(all_counties)
    target_county = all_counties[target_idx]
    target_id = target_county["id"]

    if token:
        try:
            payload = decrypt_session_token(token)
            if payload.get("seed") == effective_seed:
                payload_target_id = payload.get("target_id", target_id)
                target = get_county_by_id(payload_target_id) or target_county
                guesses_ids = payload.get("guesses", [])

                reconstructed_guesses: list[PowiatHeraldryGuessResult] = []
                for idx, gid in enumerate(guesses_ids):
                    g_county = get_county_by_id(gid)
                    if not g_county:
                        continue
                    g_made = idx + 1
                    g_rem = max(0, 8 - g_made)
                    g_correct = gid == target["id"]
                    g_won = g_correct
                    g_over = g_won or (g_made >= 8)
                    g_same_voivodeship = (
                        g_county["voivodeship"].strip().lower()
                        == target["voivodeship"].strip().lower()
                    )

                    if g_correct:
                        g_dist = 0
                        g_deg = None
                        g_dir = None
                        g_arr = None
                    else:
                        g_dist = calculate_distance_km(
                            g_county["latitude"],
                            g_county["longitude"],
                            target["latitude"],
                            target["longitude"],
                        )
                        g_deg, g_dir, g_arr = calculate_bearing(
                            g_county["latitude"],
                            g_county["longitude"],
                            target["latitude"],
                            target["longitude"],
                        )

                    wrong_so_far = [x for x in guesses_ids[:g_made] if x != target["id"]]
                    g_plates = None
                    if (not g_correct and len(wrong_so_far) >= 5) or g_over:
                        g_plates = get_registration_plates(target["id"])

                    g_target_obj = None
                    g_attr = None
                    if g_over:
                        g_target_obj = PowiatHeraldryTarget(
                            id=target["id"],
                            name=target["name"],
                            voivodeship=target["voivodeship"],
                        )
                        g_attr = get_source_attribution(target["id"], target["name"])

                    partial_token = encrypt_session_token(
                        {
                            "seed": payload["seed"],
                            "is_daily": payload["is_daily"],
                            "date": payload["date"],
                            "target_id": target["id"],
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
                            token=partial_token,
                        )
                    )

                won = any(gid == target["id"] for gid in guesses_ids)
                is_game_over = won or (len(guesses_ids) >= 8)
                wrong_guesses = [gid for gid in guesses_ids if gid != target["id"]]

                registration_plates = None
                if len(wrong_guesses) >= 5 or is_game_over:
                    registration_plates = get_registration_plates(target["id"])

                target_powiat_obj = None
                source_attr = None
                if is_game_over:
                    target_powiat_obj = PowiatHeraldryTarget(
                        id=target["id"],
                        name=target["name"],
                        voivodeship=target["voivodeship"],
                    )
                    source_attr = get_source_attribution(target["id"], target["name"])

                return PowiatHeraldryChallenge(
                    seed=effective_seed,
                    is_daily=is_daily,
                    date=payload.get("date", today_str),
                    max_guesses=8,
                    hint_unlock_guesses=5,
                    token=token,
                    coat_asset_url=f"/powiatdle/heraldry/coat-asset?token={token}",
                    source_attribution=source_attr,
                    guesses=reconstructed_guesses,
                    is_game_over=is_game_over,
                    won=won,
                    registration_plates=registration_plates,
                    target_powiat=target_powiat_obj,
                )
        except HTTPException:
            pass

    # Fresh session token
    fresh_payload = {
        "seed": effective_seed,
        "is_daily": is_daily,
        "date": today_str,
        "target_id": target_id,
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
        coat_asset_url=f"/powiatdle/heraldry/coat-asset?token={fresh_token}",
        source_attribution=None,
        guesses=[],
        is_game_over=False,
        won=False,
        registration_plates=None,
        target_powiat=None,
    )


@router.get("/coat-asset")
async def get_coat_asset(token: str = Query(...)):
    """Streams the coat of arms SVG for the session target county."""
    payload = decrypt_session_token(token)
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

    svg_bytes = await asyncio.to_thread(get_or_fetch_herb_svg, target_id, county["name"])
    return Response(content=svg_bytes, media_type="image/svg+xml")


@router.post("/guess", response_model=PowiatHeraldryGuessResult)
async def make_guess(body: PowiatHeraldryGuessRequest):
    """Evaluates a guess in Powiat Heraldry mode."""
    payload = decrypt_session_token(body.token)
    target_id = payload.get("target_id")
    target_county = get_county_by_id(target_id)
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

    guessed_county = resolve_guessed_county(body.guess, body.powiat_id)
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

    guesses.append(guessed_id)
    payload["guesses"] = guesses
    guesses_made = len(guesses)
    remaining_guesses = max(0, 8 - guesses_made)

    is_correct = guessed_id == target_id
    won = is_correct
    is_game_over = won or (guesses_made >= 8)

    same_voivodeship = (
        guessed_county["voivodeship"].strip().lower()
        == target_county["voivodeship"].strip().lower()
    )

    if is_correct:
        distance_km = 0
        bearing_degrees = None
        bearing_direction = None
        bearing_arrow = None
    else:
        distance_km = calculate_distance_km(
            guessed_county["latitude"],
            guessed_county["longitude"],
            target_county["latitude"],
            target_county["longitude"],
        )
        deg, direction, arrow = calculate_bearing(
            guessed_county["latitude"],
            guessed_county["longitude"],
            target_county["latitude"],
            target_county["longitude"],
        )
        bearing_degrees = deg
        bearing_direction = direction
        bearing_arrow = arrow

    if (not is_correct and guesses_made >= 5) or is_game_over:
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
        source_attr = get_source_attribution(target_id, target_county["name"])

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
        token=new_token,
    )
