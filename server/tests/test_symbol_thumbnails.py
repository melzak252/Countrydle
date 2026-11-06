"""Symbol rendition HTTP contracts using isolated, real images."""
import hashlib
import io
import json

import pytest
from PIL import Image

from powiatdle import flag_catalog, heraldry
from regional_symbols import catalog
from tests.test_regional_symbols_api import _write_scope


@pytest.fixture
def symbol_assets(tmp_path, monkeypatch):
    _write_scope(tmp_path, 'london_boroughs', [('Bexley', 'Bex'), ('Brent', 'Brent borough'), ('Camden', 'Cam')])
    monkeypatch.setattr(catalog, 'DATA_ROOT', tmp_path)
    catalog.clear_caches()
    flags = tmp_path / 'flag_assets'
    flags.mkdir()
    original = flags / '1.svg'
    original.write_text('<svg xmlns="http://www.w3.org/2000/svg"><rect width="4" height="8" fill="blue"/></svg>')
    record = {'id': 1, 'filename': original.name, 'source': {'url': 'https://example.org/flag', 'license': 'public domain', 'asset_sha1': hashlib.sha1(original.read_bytes()).hexdigest()}}
    monkeypatch.setattr(flag_catalog, 'ASSET_DIR', flags)
    monkeypatch.setattr(flag_catalog, 'load_catalog', lambda: {1: record})
    monkeypatch.setattr(heraldry, 'get_all_counties', lambda: [{'id': 1, 'name': 'Test', 'voivodeship': 'Test', 'is_city_county': False}])
    for directory, mode, records in [(tmp_path, 'flag', [record]), (tmp_path / 'london_boroughs', 'coat', list(catalog.load_catalog('london_boroughs', 'coat').values()))]:
        for subdir, size in [('thumbnails' if mode == 'coat' else 'flag_thumbnails', 256), ('previews' if mode == 'coat' else 'flag_previews', 512)]:
            destination = directory / subdir
            destination.mkdir()
            manifest = {}
            for item in records:
                image = io.BytesIO()
                Image.new('RGB', (size // 2, size), 'red' if mode == 'coat' else 'blue').save(image, format='WEBP', lossless=True)
                data = image.getvalue()
                name = f"{mode}-{item['id']}.webp"
                (destination / name).write_bytes(data)
                manifest[str(item['id'])] = {'filename': name, 'source_sha1': item['source']['asset_sha1'], 'sha256': hashlib.sha256(data).hexdigest()}
            (destination / f'{mode}-manifest.json').write_text(json.dumps(manifest))
    heraldry.thumbnail_manifest.cache_clear()
    yield
    catalog.clear_caches()
    heraldry.thumbnail_manifest.cache_clear()


@pytest.mark.anyio
@pytest.mark.parametrize('base', ['/powiatdle/flags', '/regional-symbols/london_boroughs/coat'])
async def test_catalog_thumbnail_is_small_and_immutable(async_client, symbol_assets, base):
    response = await async_client.get(f'{base}/catalog')
    assert response.status_code == 200
    item = response.json()[0]
    url = item['thumbnail_asset_url']
    assert url != item['flag_asset_url']
    image = await async_client.get(url)
    assert image.status_code == 200
    with Image.open(io.BytesIO(image.content)) as decoded:
        assert decoded.format == 'WEBP'
        assert 0 < decoded.width <= 256 and 0 < decoded.height <= 256
        pixel = decoded.convert('RGB').getpixel((0, 0))
        assert pixel[2 if base == '/powiatdle/flags' else 0] > 220
    assert image.headers['content-type'].startswith('image/webp')
    assert image.headers['cache-control'] == 'public, max-age=31536000, immutable'
    digest = hashlib.sha256(image.content).hexdigest()
    assert digest in url
    assert (await async_client.get(url.replace(digest, 'stale'))).status_code == 404
