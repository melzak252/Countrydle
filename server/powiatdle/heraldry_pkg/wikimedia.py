"""SVG sanitization, atomic cache I/O, and Wikimedia/Wikipedia heraldry fetching."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Optional

from powiatdle.heraldry_pkg.catalog import clean_html
from powiatdle.heraldry_pkg.schemas import facade_attr

USER_AGENT = "CountrydleHeraldryBot/1.0 (https://countrydle.com; heraldry@countrydle.com)"


def _svg_absolute_length(value: str) -> Optional[float]:
    match = re.fullmatch(
        r"\s*([+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*(px|in|cm|mm|q|pt|pc)?\s*",
        value,
        re.IGNORECASE,
    )
    if not match:
        return None
    factors = {
        "": 1,
        "px": 1,
        "in": 96,
        "cm": 96 / 2.54,
        "mm": 96 / 25.4,
        "q": 96 / 101.6,
        "pt": 96 / 72,
        "pc": 16,
    }
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

    m = re.search(r"<svg([^>]*)>", text)
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
        viewbox = (
            f"0 0 {width:.15g} {height:.15g}"
            if width is not None and height is not None
            else None
        )

    stripped_attrs = (
        r"(?:viewBox|xmlns)" if viewbox is None else r"(?:width|height|viewBox|xmlns)"
    )
    clean_attrs = re.sub(
        rf'\s+{stripped_attrs}\s*=\s*["\'][^"\']*["\']', "", attrs, flags=re.IGNORECASE
    ).strip()

    new_attrs = 'xmlns="http://www.w3.org/2000/svg"'
    if viewbox:
        new_attrs += f' viewBox="{viewbox}"'
    if clean_attrs:
        new_attrs += f" {clean_attrs}"

    new_svg_tag = f"<svg {new_attrs}>"
    text = text[: m.start()] + new_svg_tag + text[m.end() :]
    return text.encode("utf-8")


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
    facade_attr("atomic_write", atomic_write)(path, json.dumps(entry, ensure_ascii=False))


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


def resolve_and_fetch_heraldry(
    wiki_title: str, filename: Optional[str] = None
) -> tuple[bytes, dict]:
    _fetch = facade_attr("fetch_url", fetch_url)
    if not filename:
        wiki_url = (
            f"https://pl.wikipedia.org/w/api.php?action=query"
            f"&titles={urllib.parse.quote(wiki_title)}&prop=pageprops|images&imlimit=50&redirects=1&format=json"
        )
        wiki_data = json.loads(_fetch(wiki_url).decode("utf-8"))
        pages = wiki_data.get("query", {}).get("pages", {})
        if not pages:
            raise ValueError(f"No Wikipedia page found for '{wiki_title}'")
        page = next(iter(pages.values()))
        qid = page.get("pageprops", {}).get("wikibase_item")
        if qid:
            wd_url = f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={qid}&props=claims&format=json"
            wd_data = json.loads(_fetch(wd_url).decode("utf-8"))
            claims = wd_data.get("entities", {}).get(qid, {}).get("claims", {})
            p94 = claims.get("P94")
            if p94:
                filename = p94[0].get("mainsnak", {}).get("datavalue", {}).get("value")
        if not filename:
            filename = _extract_wiki_fallback_coat_filename(wiki_title, page)
        if not filename:
            raise ValueError(
                f"No coat of arms filename found on Wikidata ({qid}) or Wikipedia for '{wiki_title}'"
            )

    commons_title = f"File:{filename}"
    commons_url = (
        f"https://commons.wikimedia.org/w/api.php?action=query"
        f"&titles={urllib.parse.quote(commons_title)}&prop=imageinfo&iiprop=url|extmetadata&format=json"
    )
    c_bytes = _fetch(commons_url)
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

    svg_download_url = (
        file_url
        or f"https://commons.wikimedia.org/wiki/Special:FilePath/{urllib.parse.quote(filename)}"
    )
    svg_bytes = sanitize_svg_bytes(_fetch(svg_download_url))
    if not svg_bytes or (b"<svg" not in svg_bytes and b"<?xml" not in svg_bytes):
        raise ValueError(f"Downloaded file for '{filename}' is not valid SVG content")

    meta = {
        "filename": filename,
        "url": file_url or svg_download_url,
        "attribution": attr,
    }
    return svg_bytes, meta
