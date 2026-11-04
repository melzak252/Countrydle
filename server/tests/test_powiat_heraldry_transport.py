import gzip

import pytest
from fastapi import HTTPException

from powiatdle.heraldry import encrypt_session_token


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("accept_encoding", "compressed"),
    [
        ("identity", False),
        ("gzip", True),
        ("br, GZip; q=0.5", True),
        ("gzip;q=0", False),
        ("gzip;q=0, *;q=1", False),
        ("br, *;q=0.5", True),
        ("gzip;q=0.0", False),
    ],
)
async def test_coat_asset_negotiates_gzip(async_client, monkeypatch, accept_encoding, compressed):
    svg = b'<svg xmlns="http://www.w3.org/2000/svg">' + b'<path d="M 1 2"/>' * 2000 + b'</svg>'
    monkeypatch.setattr('powiatdle.heraldry.get_county_by_id', lambda _: {'name': 'test'})
    monkeypatch.setattr('powiatdle.heraldry.get_or_fetch_herb_svg', lambda *_: svg)
    token = encrypt_session_token({'target_id': 1})
    async with async_client.stream('GET', '/powiatdle/heraldry/coat-asset', params={'token': token}, headers={'Accept-Encoding': accept_encoding}) as response:
        wire = b''.join([part async for part in response.aiter_raw()])
        assert response.status_code == 200
        assert response.headers['content-type'].startswith('image/svg+xml')
        assert 'accept-encoding' in response.headers['vary'].lower()
        assert response.headers.get('content-encoding') == ('gzip' if compressed else None)
        assert (gzip.decompress(wire) if compressed else wire) == svg
        if compressed:
            assert len(wire) < len(svg)


@pytest.mark.anyio
async def test_coat_asset_errors_are_not_cached_or_compressed(async_client, monkeypatch):
    bad = await async_client.get('/powiatdle/heraldry/coat-asset', params={'token': 'invalid'}, headers={'Accept-Encoding': 'gzip'})
    assert bad.status_code == 403
    assert 'cache-control' not in bad.headers
    assert 'content-encoding' not in bad.headers

    monkeypatch.setattr('powiatdle.heraldry.get_county_by_id', lambda _: {'name': 'test'})
    def unavailable(*_):
        raise HTTPException(status_code=503, detail='Coat of arms asset temporarily unavailable.')
    monkeypatch.setattr('powiatdle.heraldry.get_or_fetch_herb_svg', unavailable)
    token = encrypt_session_token({'target_id': 1})
    failure = await async_client.get('/powiatdle/heraldry/coat-asset', params={'token': token}, headers={'Accept-Encoding': 'gzip'})
    assert failure.status_code == 503
    assert failure.json()['detail'] == 'Coat of arms asset temporarily unavailable.'
    assert 'cache-control' not in failure.headers
    assert 'content-encoding' not in failure.headers
