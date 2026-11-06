"""Verified, locally packaged county flags."""
import json
from pathlib import Path
from functools import lru_cache
from urllib.parse import urlparse

from fastapi import HTTPException

CATALOG_PATH = Path(__file__).with_name("flags_catalog.json")
ASSET_DIR = Path(__file__).with_name("flag_assets")
DAILY_V1_PATH = Path(__file__).with_name("flags_daily_v1.json")

def _https_url(value) -> bool:
    if not isinstance(value, str):
        return False
    url = urlparse(value)
    return url.scheme == "https" and bool(url.netloc)


def _valid_source(source) -> bool:
    if not isinstance(source, dict) or not _https_url(source.get("url")):
        return False
    license_name = source.get("license")
    if not isinstance(license_name, str) or not license_name.strip():
        return False
    if license_name.strip().casefold() == "public domain":
        return True
    author = source.get("attribution")
    return isinstance(author, str) and bool(author.strip()) and _https_url(source.get("license_url"))




def load_catalog() -> dict[int, dict]:
    return _load_catalog(CATALOG_PATH, ASSET_DIR)


@lru_cache(maxsize=None)
def _load_catalog(catalog_path: Path, asset_dir: Path) -> dict[int, dict]:
    try:
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("build_complete") is not True:
            raise ValueError("Flag catalog is not published")
        records = data["counties"]
        if not isinstance(records, list):
            raise ValueError("Invalid flag catalog")
        result = {}
        for record in records:
            county_id = record["id"]
            filename = record["filename"]
            if (type(county_id) is not int or not isinstance(filename, str)
                    or not filename or Path(filename).name != filename
                    or not _valid_source(record["source"])
                    or not (asset_dir / filename).is_file() or county_id in result):
                raise ValueError("Invalid flag catalog entry")
            result[county_id] = record
        if not result:
            raise ValueError("Empty flag catalog")
        return result
    except (OSError, ValueError, TypeError, KeyError):
        raise HTTPException(status_code=503, detail="Flag catalog unavailable.")


def load_daily_ids() -> list[int]:
    """Read the immutable v1 daily pool, independent of catalog expansions."""
    return _load_daily_ids(DAILY_V1_PATH)


@lru_cache(maxsize=None)
def _load_daily_ids(path: Path) -> list[int]:
    try:
        ids = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(ids, list) or not ids or
                any(type(county_id) is not int for county_id in ids) or
                len(set(ids)) != len(ids)):
            raise ValueError("Invalid daily flag pool")
        return ids
    except (OSError, ValueError, TypeError):
        raise HTTPException(status_code=503, detail="Flag daily pool unavailable.")
