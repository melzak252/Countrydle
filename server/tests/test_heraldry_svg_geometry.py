import json
import base64
import xml.etree.ElementTree as ET
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from powiatdle.heraldry import (
    get_or_fetch_herb_svg,
    get_or_fetch_herb_thumb,
    get_source_attribution,
    sanitize_svg_bytes,
    write_heraldry_cache,
)
from scripts.build_powiat_heraldry import verify_entry


@pytest.mark.parametrize(
    ('width', 'height', 'expected'),
    [
        ('600pt', '710pt', (800, 710 * 96 / 72)),
        ('100px', '400px', (100, 400)),
        ('4in', '2in', (384, 192)),
        ('25.4mm', '2.54cm', (96, 96)),
        ('40Q', '6pc', (40 * 96 / 101.6, 96)),
        ('120', '60', (120, 60)),
    ],
)
def test_svg_absolute_dimensions_become_correct_user_space_viewbox(width, height, expected):
    source = f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><rect width="100%" height="100%"/></svg>'.encode()
    root = ET.fromstring(sanitize_svg_bytes(source))
    x, y, w, h = map(float, root.get('viewBox').split())
    assert (x, y) == (0, 0)
    assert (w, h) == pytest.approx(expected)


def test_existing_viewbox_is_preserved():
    root = ET.fromstring(sanitize_svg_bytes(b'<svg width="600pt" height="710pt" viewBox="-10 -20 900 1100"></svg>'))
    assert root.get('viewBox') == '-10 -20 900 1100'


def test_percent_dimensions_are_not_guessed_or_removed():
    root = ET.fromstring(sanitize_svg_bytes(b'<svg width="100%" height="50%"></svg>'))
    assert root.get('viewBox') is None
    assert root.get('width') == '100%'
    assert root.get('height') == '50%'


def test_damaged_legacy_cache_is_refetched_once_and_attribution_preserved(tmp_path):
    legacy = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 710"></svg>'
    (tmp_path / '1.svg').write_bytes(legacy)
    (tmp_path / '1.json').write_text(json.dumps({'attribution': {'title': 'old'}}))
    source = b'<svg width="600pt" height="710pt"><rect width="800" height="946"/></svg>'
    repaired = sanitize_svg_bytes(source)
    metadata = {'attribution': {'title': 'original attribution'}}
    with patch('powiatdle.heraldry.get_herb_cache_dir', return_value=tmp_path), patch(
        'powiatdle.heraldry.get_heraldry_filename', return_value=None
    ), patch(
        'powiatdle.heraldry.resolve_and_fetch_heraldry', return_value=(repaired, metadata)
    ) as fetch:
        first = get_or_fetch_herb_svg(1, 'example')
        second = get_or_fetch_herb_svg(1, 'example')
    fetch.assert_called_once_with('example', None)
    assert first == second == repaired
    assert json.loads((tmp_path / '1.json').read_text())['attribution']['title'] == 'old'
    entry = json.loads((tmp_path / '1.v2.json').read_text())
    assert entry == {'svg': repaired.decode(), 'metadata': metadata}
    with patch('powiatdle.heraldry.get_herb_cache_dir', return_value=tmp_path):
        assert get_source_attribution(1, 'example').title == 'original attribution'
    assert (tmp_path / '1.svg').read_bytes() == legacy


def test_damaged_legacy_cache_is_not_served_when_refetch_fails(tmp_path):
    (tmp_path / '1.svg').write_bytes(b'<svg viewBox="0 0 600 710"></svg>')
    with patch('powiatdle.heraldry.get_herb_cache_dir', return_value=tmp_path), patch(
        'powiatdle.heraldry.resolve_and_fetch_heraldry', side_effect=RuntimeError('unavailable')
    ), pytest.raises(HTTPException) as error:
        get_or_fetch_herb_svg(1, 'example')
    assert error.value.status_code == 503


def test_failed_publication_cannot_serve_svg_with_legacy_attribution(tmp_path):
    (tmp_path / '1.json').write_text(json.dumps({'attribution': {'title': 'old'}}))
    repaired = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 946"></svg>'
    metadata = {'attribution': {'title': 'new'}}
    from powiatdle.heraldry import atomic_write

    def fail_json(path, content):
        if path.suffix == '.json':
            raise OSError('disk failure')
        return atomic_write(path, content)

    with patch('powiatdle.heraldry.get_herb_cache_dir', return_value=tmp_path), patch(
        'powiatdle.heraldry.resolve_and_fetch_heraldry', return_value=(repaired, metadata)
    ), patch('powiatdle.heraldry.atomic_write', side_effect=fail_json):
        with pytest.raises(HTTPException) as error:
            get_or_fetch_herb_svg(1, 'example')
        assert error.value.status_code == 503
        assert get_source_attribution(1, 'example') is None


def test_builder_verifies_atomic_entry_not_legacy_files(tmp_path):
    (tmp_path / '1.svg').write_text('<svg>' + ' ' * 50 + '</svg>')
    (tmp_path / '1.json').write_text(json.dumps({'attribution': {'title': 'old'}}))
    cache_file = tmp_path / '1.v2.json'
    assert not verify_entry(cache_file)[0]
    write_heraldry_cache(cache_file, b'<svg>' + b' ' * 50 + b'</svg>', {'attribution': {'title': 'new'}})
    assert verify_entry(cache_file)[0]


def test_thumbnail_filename_fallback_uses_atomic_entry(tmp_path):
    (tmp_path / '1.json').write_text(json.dumps({'filename': 'old.svg'}))
    write_heraldry_cache(tmp_path / '1.v2.json', b'<svg></svg>', {
        'filename': 'new.svg', 'attribution': {'title': 'new'},
    })
    png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')
    with patch('powiatdle.heraldry.get_herb_cache_dir', return_value=tmp_path), patch(
        'powiatdle.heraldry.get_heraldry_filename', return_value=None
    ), patch('powiatdle.heraldry.fetch_url', return_value=png) as fetch:
        assert get_or_fetch_herb_thumb(1, 'example') == (png, 'image/png')
    assert 'new.svg' in fetch.call_args.args[0]
