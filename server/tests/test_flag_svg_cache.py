from __future__ import annotations

from io import BytesIO
from pathlib import Path
from threading import get_ident
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import flagdle


SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><rect fill="#fff"/></svg>'


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    directory = tmp_path / "flag_svg_cache"
    monkeypatch.setattr(flagdle, "FLAG_SVG_CACHE_DIR", directory)
    return directory


def test_cached_flag_is_available_without_upstream_after_restart(tmp_path, monkeypatch):
    (tmp_path / "pl.svg").write_bytes(SVG)
    monkeypatch.setattr(flagdle, "FLAG_SVG_CACHE_DIR", tmp_path)

    def upstream_unavailable(*args, **kwargs):
        raise OSError("upstream unavailable after restart")

    monkeypatch.setattr(flagdle.urllib.request, "urlopen", upstream_unavailable)
    assert flagdle._get_or_fetch_flag_svg("PL") == SVG


def test_downloaded_svg_persists_and_is_reused(cache_dir, monkeypatch):
    requests = []

    def download(request, timeout):
        requests.append(request.full_url)
        assert timeout == 5
        return BytesIO(SVG)

    monkeypatch.setattr(flagdle.urllib.request, "urlopen", download)
    assert flagdle._get_or_fetch_flag_svg("PL") == SVG
    assert (cache_dir / "pl.svg").read_bytes() == SVG
    assert flagdle._get_or_fetch_flag_svg("pl") == SVG
    assert requests == ["https://flagcdn.com/pl.svg"]

    # The disk remains authoritative even after the flag was served by this worker.
    replacement = b'<svg xmlns="http://www.w3.org/2000/svg"><rect fill="#f00"/></svg>'
    (cache_dir / "pl.svg").write_bytes(replacement)
    assert flagdle._get_or_fetch_flag_svg("PL") == replacement
    assert len(requests) == 1


def test_temporary_upstream_failure_does_not_cache_fallback(cache_dir, monkeypatch):
    attempts = 0

    def download(request, timeout):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("temporary upstream outage")
        return BytesIO(SVG)

    monkeypatch.setattr(flagdle.urllib.request, "urlopen", download)
    fallback = flagdle._get_or_fetch_flag_svg("pl")
    assert b"Flag of PL" in fallback
    assert not (cache_dir / "pl.svg").exists()
    assert flagdle._get_or_fetch_flag_svg("pl") == SVG
    assert (cache_dir / "pl.svg").read_bytes() == SVG
    assert attempts == 2


def test_failed_atomic_publication_returns_real_flag_and_cleans_tempfile(
    cache_dir, monkeypatch, caplog
):
    monkeypatch.setattr(flagdle.urllib.request, "urlopen", lambda *a, **kw: BytesIO(SVG))

    def failed_replace(source, destination):
        assert Path(source).parent == cache_dir
        assert Path(source).read_bytes() == SVG
        assert Path(destination) == cache_dir / "pl.svg"
        assert not Path(destination).exists()
        raise OSError("publication failed")

    monkeypatch.setattr(flagdle.os, "replace", failed_replace)
    assert flagdle._get_or_fetch_flag_svg("pl") == SVG
    assert list(cache_dir.iterdir()) == []
    assert "publication failed" in caplog.text


def test_unavailable_cache_directory_does_not_hide_downloaded_flag(cache_dir, monkeypatch, caplog):
    cache_dir.write_bytes(b"not a directory")
    monkeypatch.setattr(flagdle.urllib.request, "urlopen", lambda *a, **kw: BytesIO(SVG))
    assert flagdle._get_or_fetch_flag_svg("pl") == SVG
    assert cache_dir.read_bytes() == b"not a directory"
    assert "Failed to read cached SVG" in caplog.text
    assert "Failed to cache SVG" in caplog.text


@pytest.mark.parametrize("code", ["../pl", "/pl", "pl/../../fr", "", "p", "pol", "pł"])
def test_invalid_iso2_cannot_escape_cache_path(code, cache_dir, monkeypatch):
    def unexpected_download(*args, **kwargs):
        pytest.fail("Invalid ISO2 must be rejected before accessing upstream")

    monkeypatch.setattr(flagdle.urllib.request, "urlopen", unexpected_download)
    fallback = flagdle._get_or_fetch_flag_svg(code)
    assert f"Flag of {code.upper()}".encode("utf-8") in fallback
    assert not cache_dir.exists()


@pytest.mark.anyio
async def test_authorized_asset_serves_download_off_event_loop_and_rejects_invalid_token(
    async_client, cache_dir, monkeypatch
):
    day = SimpleNamespace(id=55, country=SimpleNamespace(name="Poland"))
    monkeypatch.setattr(
        flagdle.FlagdleDayRepository, "get_today_flag", AsyncMock(return_value=day)
    )
    event_loop_thread = get_ident()
    downloads = []

    def download(request, timeout):
        assert get_ident() != event_loop_thread
        downloads.append(request.full_url)
        return BytesIO(SVG)

    monkeypatch.setattr(flagdle.urllib.request, "urlopen", download)
    rejected = await async_client.get("/flagdle/flag-asset?token=invalid_token")
    assert rejected.status_code == 403
    assert not cache_dir.exists()
    assert downloads == []

    token = flagdle.generate_asset_token(day.id)
    response = await async_client.get(f"/flagdle/flag-asset?token={token}")
    assert response.status_code == 200
    assert response.content == SVG
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert response.headers["cache-control"] == "public, max-age=3600"
    assert (cache_dir / "pl.svg").read_bytes() == SVG
    assert downloads == ["https://flagcdn.com/pl.svg"]


@pytest.mark.anyio
async def test_unknown_country_asset_keeps_uncached_generic_fallback(
    async_client, cache_dir, monkeypatch
):
    day = SimpleNamespace(id=55, country=SimpleNamespace(name="Unknown country"))
    monkeypatch.setattr(
        flagdle.FlagdleDayRepository, "get_today_flag", AsyncMock(return_value=day)
    )

    def unexpected_download(*args, **kwargs):
        pytest.fail("Unknown country must not fetch a guessed flag URL")

    monkeypatch.setattr(flagdle.urllib.request, "urlopen", unexpected_download)
    token = flagdle.generate_asset_token(day.id)
    response = await async_client.get(f"/flagdle/flag-asset?token={token}")
    assert response.status_code == 200
    assert b"Flag of " in response.content
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert response.headers["cache-control"] == "public, max-age=3600"
    assert not cache_dir.exists()
