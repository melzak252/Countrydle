"""Locally packaged, independently audited regional symbol pools."""
import json
import math
import unicodedata
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException
from powiatdle.flag_catalog import _https_url, _valid_source

DATA_ROOT = Path(__file__).parent / 'data'
SCOPES = {'voivodeships', 'london_boroughs', 'england_counties'}
MODES = {'coat': 'coats', 'flag': 'flags'}


def normalize(value: str) -> str:
    value = value.casefold().replace('ł', 'l')
    value = ''.join(c for c in unicodedata.normalize('NFKD', value) if not unicodedata.combining(c))
    return ' '.join(value.replace('-', ' ').replace('–', ' ').split())


def _valid_component_credits(source):
    credits = source.get('component_credits', [])
    if not isinstance(credits, list):
        return False
    for credit in credits:
        if (not isinstance(credit, dict) or not _https_url(credit.get('url'))
                or any(not isinstance(credit.get(key), str) or not credit[key].strip()
                       for key in ('title', 'author', 'license'))):
            return False
        if credit['license'].strip().casefold() != 'public domain' and not _https_url(credit.get('license_url')):
            return False
    return True


def _directory(scope):
    if scope not in SCOPES:
        raise HTTPException(status_code=404, detail='Unknown geography.')
    return DATA_ROOT / scope


def _read(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise HTTPException(status_code=503, detail='Regional catalog unavailable.')


@lru_cache(maxsize=None)
def load_entities(scope):
    directory = _directory(scope)
    try:
        records = _read(directory / 'entities.json')['entities']
        if not isinstance(records, list) or not records:
            raise ValueError()
        result, names = {}, {}
        for record in records:
            id_, name = record['id'], record['name']
            aliases = record['aliases']
            if (type(id_) is not int or id_ <= 0 or id_ in result or not isinstance(name, str)
                    or not name.strip() or not isinstance(aliases, list)
                    or any(not isinstance(alias, str) or not alias.strip() for alias in aliases)
                    or not isinstance(record['point_source'], str) or not record['point_source'].strip()):
                raise ValueError()
            lat, lon = record['latitude'], record['longitude']
            if (type(lat) not in (int, float) or type(lon) not in (int, float)
                    or not math.isfinite(lat) or not math.isfinite(lon)
                    or not -90 <= lat <= 90 or not -180 <= lon <= 180):
                raise ValueError()
            for form in [name, *aliases]:
                key = normalize(form)
                if not key or (key in names and names[key] != id_):
                    raise ValueError()
                names[key] = id_
            result[id_] = record
        return result
    except (ValueError, TypeError, KeyError):
        raise HTTPException(status_code=503, detail='Regional entity catalog unavailable.')


@lru_cache(maxsize=None)
def load_catalog(scope, mode):
    directory = _directory(scope)
    if mode not in MODES:
        raise HTTPException(status_code=404, detail='Unknown symbol.')
    try:
        data = _read(directory / f'{MODES[mode]}_catalog.json')
        records = data['entities']
        if data['build_complete'] is not True or not isinstance(records, list) or len(records) < 2:
            raise ValueError()
        entities, result = load_entities(scope), {}
        for record in records:
            id_, filename = record['id'], record['filename']
            if (type(id_) is not int or id_ not in entities or id_ in result
                    or not isinstance(filename, str) or not filename or Path(filename).name != filename
                    or not _valid_source(record['source']) or not _valid_component_credits(record['source'])
                    or not (directory / 'assets' / filename).is_file()):
                raise ValueError()
            result[id_] = record
        return result
    except (ValueError, TypeError, KeyError):
        raise HTTPException(status_code=503, detail='Regional symbol catalog unavailable.')


@lru_cache(maxsize=None)
def load_daily_ids(scope, mode):
    directory = _directory(scope)
    if mode not in MODES:
        raise HTTPException(status_code=404, detail='Unknown symbol.')
    ids = _read(directory / f'daily_{MODES[mode]}_v1.json')
    catalog = load_catalog(scope, mode)
    if (not isinstance(ids, list) or len(ids) < 2 or any(type(i) is not int or i not in catalog for i in ids)
            or len(set(ids)) != len(ids)):
        raise HTTPException(status_code=503, detail='Regional daily pool unavailable.')
    return ids


def clear_caches():
    load_entities.cache_clear()
    load_catalog.cache_clear()
    load_daily_ids.cache_clear()
