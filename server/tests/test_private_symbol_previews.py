import io

import pytest
from PIL import Image

from powiatdle.heraldry import encrypt_session_token
from tests.test_symbol_thumbnails import symbol_assets


@pytest.mark.anyio
@pytest.mark.parametrize(('url', 'payload', 'channel'), [
    ('/powiatdle/flags/flag-asset', {'target_id': 1, 'symbol_mode': 'flag'}, 2),
    ('/regional-symbols/london_boroughs/coat/session-asset', {'target_id': 1, 'symbol_mode': 'coat', 'entity_scope': 'london_boroughs'}, 0),
])
async def test_private_preview_and_original_on_intent(async_client, symbol_assets, url, payload, channel):
    token = encrypt_session_token(payload)
    preview = await async_client.get(url, params={'token': token})
    assert preview.status_code == 200
    assert preview.headers['cache-control'] == 'private, no-store'
    assert preview.headers['content-type'].startswith('image/webp')
    with Image.open(io.BytesIO(preview.content)) as image:
        assert image.format == 'WEBP' and max(image.size) <= 512
        assert image.convert('RGB').getpixel((0, 0))[channel] > 220
    original = await async_client.get(url, params={'token': token, 'full': 'true'})
    assert original.status_code == 200
    assert original.headers['cache-control'] == 'private, no-store'
    assert original.headers['content-type'].startswith('image/svg+xml')
    assert original.content.startswith(b'<svg')
