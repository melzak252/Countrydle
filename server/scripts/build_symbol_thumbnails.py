"""Build bounded quiz renditions from the audited, locally packaged symbol assets.

Requires the system GI Rsvg/cairo bindings and Pillow with WebP support. No network
access is needed. The manifests bind each rendition to both source and output bytes.
"""
import hashlib
import io
import json
import math
import re
import sys
from pathlib import Path

import cairo
import gi
from PIL import Image

gi.require_version('Rsvg', '2.0')
from gi.repository import Rsvg  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MAX_SIDE = 256


def thumbnail(source: Path, max_side: int = MAX_SIDE) -> bytes:
    data = source.read_bytes()
    if source.suffix.lower() == '.svg':
        text = data.decode('utf-8')
        for ref in re.findall(r'(?:href|src)\s*=\s*["\']([^"\']+)', text, flags=re.I):
            if not ref.startswith(('#', 'data:')):
                raise ValueError(f'External SVG reference in {source}: {ref}')
        for ref in re.findall(r'url\(\s*["\']?([^)"\']+)', text, flags=re.I):
            if not ref.strip().startswith(('#', 'data:')):
                raise ValueError(f'External CSS reference in {source}: {ref}')
        handle = Rsvg.Handle.new_from_data(data)
        valid, width, height = handle.get_intrinsic_size_in_pixels()
        if not valid:
            _, _, _, _, has_viewbox, viewbox = handle.get_intrinsic_dimensions()
            if not has_viewbox:
                raise ValueError(f'SVG has no usable dimensions: {source}')
            width, height = viewbox.width, viewbox.height
        if not (math.isfinite(width) and math.isfinite(height) and width > 0 and height > 0):
            raise ValueError(f'Invalid dimensions: {source}')
        scale = max_side / max(width, height)
        w, h = max(1, round(width * scale)), max(1, round(height * scale))
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        viewport = Rsvg.Rectangle()
        viewport.x = viewport.y = 0
        viewport.width, viewport.height = w, h
        handle.render_document(cairo.Context(surface), viewport)
        png = io.BytesIO()
        surface.write_to_png(png)
        png.seek(0)
        image = Image.open(png).convert('RGBA')
    else:
        image = Image.open(io.BytesIO(data)).convert('RGBA')
        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(output, format='WEBP', quality=85, method=6, exact=True)
    return output.getvalue()


def build(records, assets: Path, destination: Path, prefix: str, max_side: int = MAX_SIDE):
    destination.mkdir(parents=True, exist_ok=True)
    entries = {}
    for record in records:
        source = assets / record['filename']
        source_hash = hashlib.sha1(source.read_bytes()).hexdigest()
        expected = record['source'].get('asset_sha1') or record['source'].get('sha1')
        if source_hash != expected:
            raise ValueError(f'Source digest mismatch: {source}')
        result = thumbnail(source, max_side)
        name = f"{prefix}-{record['id']}.webp"
        (destination / name).write_bytes(result)
        entries[str(record['id'])] = {'filename': name, 'source_sha1': source_hash,
                                      'sha256': hashlib.sha256(result).hexdigest()}
    (destination / f'{prefix}-manifest.json').write_text(
        json.dumps(entries, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
    print(f'{destination} {prefix}: {len(entries)} renditions')


def build_county_coats():
    client = ROOT.parent / 'client'
    destination = client / 'public' / 'assets' / 'county-coats'
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for county_id in range(1, 381):
        result = thumbnail(client / 'public' / 'coats' / f'{county_id}.png')
        digest = hashlib.sha256(result).hexdigest()
        name = f'{county_id}-{digest}.webp'
        if not (destination / name).exists():
            (destination / name).write_bytes(result)
        manifest[str(county_id)] = f'/assets/county-coats/{name}'
    (client / 'src' / 'data' / 'coat_thumbnails.json').write_text(
        json.dumps(manifest, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
    print(f'{destination}: {len(manifest)} renditions')


def main():
    if sys.argv[1:] == ['--county-coats']:
        build_county_coats()
        return
    daily_only = sys.argv[1:] == ['--daily']
    if sys.argv[1:] and not daily_only:
        raise SystemExit('Usage: build_symbol_thumbnails.py [--county-coats|--daily]')
    if not daily_only:
        build_county_coats()
    flags = ROOT / 'powiatdle'
    data = json.loads((flags / 'flags_catalog.json').read_text(encoding='utf-8'))
    if not daily_only:
        build(data['counties'], flags / 'flag_assets', flags / 'flag_thumbnails', 'flag')
    build(data['counties'], flags / 'flag_assets', flags / 'flag_previews', 'flag', 512)
    for catalog in sorted((ROOT / 'regional_symbols' / 'data').glob('*/*_catalog.json')):
        data = json.loads(catalog.read_text(encoding='utf-8'))
        mode = 'coat' if catalog.name.startswith('coats_') else 'flag'
        if not daily_only:
            build(data['entities'], catalog.parent / 'assets', catalog.parent / 'thumbnails', mode)
        build(data['entities'], catalog.parent / 'assets', catalog.parent / 'previews', mode, 512)


if __name__ == '__main__':
    main()
