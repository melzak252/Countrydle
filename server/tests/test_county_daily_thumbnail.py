import io

import pytest
from PIL import Image

from powiatdle.heraldry import encrypt_session_token


def colored_png(color):
    buffer = io.BytesIO()
    Image.new('RGB', (8, 8), color).save(buffer, format='PNG')
    return buffer.getvalue()


def assert_color(response, channel):
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'private, no-store'
    assert response.headers['content-type'].startswith('image/webp')
    with Image.open(io.BytesIO(response.content)) as image:
        pixel = image.convert('RGB').getpixel((0, 0))
        assert pixel[channel] > 220 and all(pixel[i] < 35 for i in range(3) if i != channel)


@pytest.mark.anyio
async def test_daily_cold_thumbnail_uses_pinned_source_then_reuses_disk_cache(async_client, monkeypatch, tmp_path):
    monkeypatch.setattr('powiatdle.heraldry.get_herb_cache_dir', lambda: tmp_path)
    monkeypatch.setattr('powiatdle.heraldry.get_county_by_id', lambda _: {'name': 'Test'})
    monkeypatch.setattr('powiatdle.heraldry.get_heraldry_filename', lambda _: 'Known.svg')
    monkeypatch.setattr('powiatdle.heraldry.fetch_url', lambda url: colored_png('red') if 'Known.svg' in url else colored_png('blue'))
    token = encrypt_session_token({'target_id': 1})
    assert_color(await async_client.get('/powiatdle/heraldry/coat-asset', params={'token': token}), 0)
    def unavailable(_):
        raise OSError('offline')
    monkeypatch.setattr('powiatdle.heraldry.fetch_url', unavailable)
    assert_color(await async_client.get('/powiatdle/heraldry/coat-asset', params={'token': token}), 0)


@pytest.mark.anyio
async def test_inspection_explicitly_requests_original_without_leaking_identity(async_client, monkeypatch, tmp_path):
    from powiatdle.heraldry import write_heraldry_cache
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1" fill="red"/></svg>'
    write_heraldry_cache(tmp_path / '5.v2.json', svg, {'filename': 'Known.svg', 'attribution': {}})
    monkeypatch.setattr('powiatdle.heraldry.get_herb_cache_dir', lambda: tmp_path)
    monkeypatch.setattr('powiatdle.heraldry.get_county_by_id', lambda _: {'name': 'Test'})
    monkeypatch.setattr('powiatdle.heraldry.fetch_url', lambda _: colored_png('red'))
    token = encrypt_session_token({'target_id': 5})
    preview = await async_client.get('/powiatdle/heraldry/coat-asset', params={'token': token})
    assert_color(preview, 0)
    original = await async_client.get('/powiatdle/heraldry/coat-asset', params={'token': token, 'full': 'true'})
    assert original.status_code == 200 and original.content == svg
    assert original.headers['content-type'].startswith('image/svg+xml')
    assert original.headers['cache-control'] == 'private, no-store'


@pytest.mark.anyio
async def test_daily_preview_preserves_aspect_and_transparency(async_client, monkeypatch, tmp_path):
    source = io.BytesIO()
    Image.new('RGBA', (800, 1600), (255, 0, 0, 100)).save(source, format='PNG')
    monkeypatch.setattr('powiatdle.heraldry.get_herb_cache_dir', lambda: tmp_path)
    monkeypatch.setattr('powiatdle.heraldry.get_county_by_id', lambda _: {'name': 'Test'})
    monkeypatch.setattr('powiatdle.heraldry.get_heraldry_filename', lambda _: 'Known.svg')
    monkeypatch.setattr('powiatdle.heraldry.fetch_url', lambda *_: source.getvalue())
    response = await async_client.get('/powiatdle/heraldry/coat-asset', params={'token': encrypt_session_token({'target_id': 2})})
    with Image.open(io.BytesIO(response.content)) as image:
        assert image.size == (256, 512)
        assert image.getpixel((128, 256))[3] < 255


@pytest.mark.anyio
async def test_bad_preview_falls_back_to_cached_original_not_unrelated_image(async_client, monkeypatch, tmp_path):
    from powiatdle.heraldry import write_heraldry_cache
    original = b'<svg xmlns="http://www.w3.org/2000/svg"/>'
    write_heraldry_cache(tmp_path / '3.v2.json', original, {'filename': 'Correct.svg', 'attribution': {}})
    monkeypatch.setattr('powiatdle.heraldry.get_herb_cache_dir', lambda: tmp_path)
    monkeypatch.setattr('powiatdle.heraldry.get_county_by_id', lambda _: {'name': 'Test'})
    monkeypatch.setattr('powiatdle.heraldry.get_heraldry_filename', lambda _: 'Wrong.svg')
    def bad_source(url):
        return b'not an image' if 'Correct.svg' in url else colored_png('blue')
    monkeypatch.setattr('powiatdle.heraldry.fetch_url', bad_source)
    response = await async_client.get('/powiatdle/heraldry/coat-asset', params={'token': encrypt_session_token({'target_id': 3})})
    assert response.status_code == 200
    assert response.content == original
    assert response.headers['cache-control'] == 'private, no-store'


@pytest.mark.anyio
async def test_warm_preview_reuses_source_identity_and_invalidates_on_original_replacement(async_client, monkeypatch, tmp_path):
    from powiatdle import heraldry
    cache = tmp_path / '4.v2.json'
    svg = b'<svg>' + b' ' * 100000 + b'</svg>'
    heraldry.write_heraldry_cache(cache, svg, {'filename': 'First.svg', 'attribution': {}})
    def fetch(url):
        return colored_png('red') if 'First.svg' in url else colored_png('blue')
    monkeypatch.setattr(heraldry, 'get_herb_cache_dir', lambda: tmp_path)
    monkeypatch.setattr(heraldry, 'get_county_by_id', lambda _: {'name': 'Test'})
    monkeypatch.setattr(heraldry, 'fetch_url', fetch)
    token = encrypt_session_token({'target_id': 4})
    assert_color(await async_client.get('/powiatdle/heraldry/coat-asset', params={'token': token}), 0)
    def unavailable(_):
        raise OSError('offline')
    monkeypatch.setattr(heraldry, 'fetch_url', unavailable)
    assert_color(await async_client.get('/powiatdle/heraldry/coat-asset', params={'token': token}), 0)
    heraldry.write_heraldry_cache(cache, svg, {'filename': 'Other.svg', 'attribution': {}})
    monkeypatch.setattr(heraldry, 'fetch_url', fetch)
    assert_color(await async_client.get('/powiatdle/heraldry/coat-asset', params={'token': token}), 2)
