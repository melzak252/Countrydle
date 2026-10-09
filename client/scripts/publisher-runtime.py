"""Read-only publisher artifact delivery and public metadata freshness checks.

This standalone stdlib-only file is also the artifact transport validator:
python3 publisher-runtime.py --validate-release DIR [--assets-dir DEPLOYED_ASSETS]
"""

import argparse
import contextlib
from datetime import date, datetime, timezone
import fcntl
import hashlib
import http.server
from itertools import islice
import json
import mimetypes
import os
from pathlib import Path
import re
import signal
import threading
import time
import urllib.parse
import urllib.request

ROUTES = (
    "/", "/about", "/how-it-works", "/faq", "/explore",
    "/explore/modes/countrydle", "/explore/modes/us-states",
    "/explore/modes/wojewodztwa", "/explore/modes/powiaty",
    "/explore/modes/flagdle", "/explore/modes/europe",
    "/explore/modes/asia", "/explore/modes/africa", "/explore/modes/americas",
    "/privacy-policy", "/terms", "/cookie-policy", "/contact",
)
STATIC_ROUTES = tuple(route for route in ROUTES if route != "/explore")
GUIDE_ALIASES = {"/explore/modes/us_statedle": "/explore/modes/us-states"}
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
API_TIMEOUT = 10
MANIFEST = ".publisher-manifest.json"
UNAVAILABLE = b'<!doctype html><html lang="en"><head><meta name="robots" content="noindex"><title>Countrydle temporarily unavailable</title></head><body><h1>Publisher content temporarily unavailable</h1><p>Please try again shortly.</p></body></html>'
NOT_FOUND = b'<!doctype html><html lang="en"><head><meta name="robots" content="noindex"><title>Recap not found</title></head><body><h1>Recap not found</h1></body></html>'


class PublisherError(RuntimeError):
    pass


def origin(value):
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise PublisherError("Publisher origins must be absolute HTTP(S) URLs without credentials, query or fragment")
    return value.rstrip("/")


def backend_origin():
    return origin(os.environ.get("PUBLISHER_BACKEND_URL", "http://backend:8080"))


def poll_interval():
    seconds = float(os.environ.get("PUBLISHER_POLL_SECONDS", "60"))
    if not 5 <= seconds <= 3600:
        raise PublisherError("PUBLISHER_POLL_SECONDS must be between 5 and 3600 seconds")
    return seconds


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def fetch_bytes(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Countrydle-Publisher/1", "Accept": "application/json"})
    # Never inherit host proxy credentials, cookies or authorization.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=API_TIMEOUT) as response:
        if response.status != 200 or response.headers.get_content_type() != "application/json":
            raise PublisherError("Mandatory public API did not return JSON with HTTP 200")
        return response.read()


def utc_timestamp(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0
    except ValueError:
        return False


def post_error(post):
    """Malformed known metadata invalidates that route, not unrelated pages."""
    if not isinstance(post, dict) or type(post.get("id")) is not int:
        return "Missing article identifier"
    if not isinstance(post.get("slug"), str) or not SLUG.fullmatch(post["slug"]):
        return "Unsafe article slug"
    try:
        puzzle_date = date.fromisoformat(post["date"])
        if puzzle_date.isoformat() != post["date"] or puzzle_date >= datetime.now(timezone.utc).date():
            return "Article puzzle is not public"
    except (ValueError, KeyError, TypeError):
        return "Invalid article puzzle date"
    if any(not isinstance(post.get(field), str) or not post[field].strip() for field in ("title", "summary")):
        return "Missing article title or summary"
    if not utc_timestamp(post.get("updated_at")):
        return "Missing current article version"
    if post.get("created_at") is not None and not utc_timestamp(post["created_at"]):
        return "Invalid publication timestamp"
    return None


def published_posts(backend):
    posts = {}
    seen = set()
    received = 0
    total = None
    page = 1
    today = datetime.now(timezone.utc).date()
    while total is None or received < total:
        payload = json.loads(fetch_bytes(f"{backend}/blog?page={page}&limit=50"))
        if not isinstance(payload, dict):
            raise PublisherError("Mandatory blog index returned an invalid response")
        rows, count = payload.get("posts"), payload.get("total")
        if not isinstance(rows, list) or type(count) is not int or count < 0:
            raise PublisherError("Mandatory blog index returned an invalid response")
        if count == 0 and rows == [] and total is None:
            return {}
        if total is not None and count != total:
            raise PublisherError("Published blog list changed during pagination")
        total = count
        if not rows:
            raise PublisherError("Published blog pagination ended before its reported total")
        for post in rows:
            slug = post.get("slug") if isinstance(post, dict) else None
            if not isinstance(slug, str) or not SLUG.fullmatch(slug) or slug in seen:
                raise PublisherError("Published blog contains an unsafe or duplicate slug")
            seen.add(slug)
            received += 1
            try:
                future = date.fromisoformat(post.get("date")) >= today
            except (TypeError, ValueError):
                future = False  # Known malformed article remains a route-specific 503.
            if not future:
                posts[slug] = post
        if received > total:
            raise PublisherError("Published blog total disagrees with its results")
        page += 1
    return posts


def exploration_modes(backend):
    modes = json.loads(fetch_bytes(f"{backend}/explore/modes"))
    if not isinstance(modes, list) or not modes or any(not isinstance(mode, dict) for mode in modes):
        raise PublisherError("Mandatory exploration modes returned empty or malformed data")
    return modes


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def asset_fingerprint(assets):
    """Same shell and compiled bundle are required on capture and serving images."""
    assets = Path(assets)
    shell = assets / "spa-shell.html"
    bundle = assets / "assets"
    if not shell.is_file() or not bundle.is_dir():
        raise PublisherError("Missing immutable SPA shell or deployed assets")
    files = [shell, *(path for path in bundle.rglob("*") if path.is_file())]
    if len(files) == 1:
        raise PublisherError("Deployed asset bundle is empty")
    digest = hashlib.sha256()
    for path in sorted(files, key=lambda path: path.relative_to(assets).as_posix()):
        digest.update(path.relative_to(assets).as_posix().encode() + b"\0")
        with path.open("rb") as source:
            while block := source.read(1024 * 1024):
                digest.update(block)
        digest.update(b"\0")
    return digest.hexdigest()


def output_file(directory, route):
    return Path(directory) / route.lstrip("/") / "index.html"


def related_dependencies(posts):
    """Mirror detail API: first four list results, exclude own ID, take three."""
    recent = list(islice(posts.values(), 4))
    return {
        slug: [candidate for candidate in recent if candidate.get("id") != post.get("id")][:3]
        for slug, post in posts.items()
    }


def route_version(route, posts, modes, build):
    if route == "/explore":
        return fingerprint(modes)
    if route == "/blog":
        return fingerprint(list(posts.values()))
    if route.startswith("/blog/"):
        slug = route.removeprefix("/blog/")
        post = posts.get(slug)
        recent = list(islice(posts.values(), 4))
        related = [candidate for candidate in recent if post is not None and candidate.get("id") != post.get("id")][:3]
        return fingerprint({"post": post, "related": related})
    return build


def validate_release(release, assets=None, expected_build=None):
    """Validate transport integrity and mandatory static readiness without API I/O."""
    release = Path(release).resolve()
    try:
        manifest = json.loads((release / MANIFEST).read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or manifest.get("schema") != 1:
            raise PublisherError("Unsupported publisher artifact schema")
        build = manifest.get("build_fingerprint")
        if not isinstance(build, str) or not DIGEST.fullmatch(build):
            raise PublisherError("Missing publisher bundle fingerprint")
        if assets is not None:
            expected_build = asset_fingerprint(assets)
        if expected_build is not None and build != expected_build:
            raise PublisherError("Publisher artifact does not match deployed shell/assets")
        if not utc_timestamp(manifest.get("captured_at")):
            raise PublisherError("Missing capture timestamp")
        posts_state, modes_state = manifest.get("posts"), manifest.get("modes")
        if not isinstance(posts_state, dict) or posts_state.get("status") not in (200, 503) or not isinstance(posts_state.get("metadata"), dict):
            raise PublisherError("Missing explicit public blog availability")
        if not isinstance(modes_state, dict) or modes_state.get("status") not in (200, 503) or not isinstance(modes_state.get("metadata"), list):
            raise PublisherError("Missing explicit Explore availability")
        posts, modes = posts_state["metadata"], modes_state["metadata"]
        if any(not isinstance(slug, str) or not SLUG.fullmatch(slug) or not isinstance(post, dict) or post.get("slug") != slug for slug, post in posts.items()):
            raise PublisherError("Unsafe artifact article metadata")
        if modes_state["status"] == 200 and (not modes or any(not isinstance(mode, dict) for mode in modes)):
            raise PublisherError("Artifact claims a falsely empty Explore response")
        if json.loads((release / ".publisher-posts.json").read_text(encoding="utf-8")) != posts:
            raise PublisherError("Article metadata manifests disagree")
        routes = manifest.get("routes")
        required = {*ROUTES, "/blog", *("/blog/" + slug for slug in posts)}
        if not isinstance(routes, dict) or set(routes) != required:
            raise PublisherError("Artifact does not declare every known publisher route")
        for route, item in routes.items():
            if not isinstance(item, dict) or type(item.get("status")) is not int or item["status"] not in (200, 503):
                raise PublisherError("Invalid route availability")
            if item.get("version") != route_version(route, posts, modes, build):
                raise PublisherError("Route version disagrees with its metadata")
            if route in STATIC_ROUTES and item["status"] != 200:
                raise PublisherError("Mandatory initial static HTML is unavailable")
            target = output_file(release, route)
            if item["status"] == 503:
                if target.exists() or "sha256" in item:
                    raise PublisherError("Failed route must not retain stale or error HTML")
                continue
            if route.startswith("/blog") and posts_state["status"] != 200:
                raise PublisherError("Unavailable blog must not claim successful HTML")
            if route.startswith("/blog/") and post_error(posts[route.removeprefix("/blog/")]):
                raise PublisherError("Invalid article metadata must not claim successful HTML")
            if route == "/explore" and modes_state["status"] != 200:
                raise PublisherError("Unavailable Explore must not claim successful HTML")
            if not target.resolve().is_relative_to(release) or target.is_symlink():
                raise PublisherError("Artifact HTML escapes its immutable release")
            payload = target.read_bytes()
            sha256 = item.get("sha256")
            if not payload or not isinstance(sha256, str) or not DIGEST.fullmatch(sha256) or hashlib.sha256(payload).hexdigest() != sha256:
                raise PublisherError("Missing or corrupted publisher HTML")
            if not re.search(br"<main\b", payload, re.IGNORECASE) or not re.search(br"<h1\b", payload, re.IGNORECASE):
                raise PublisherError("Publisher artifact contains a shell instead of readable content")
        return manifest
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise PublisherError(f"Unreadable publisher artifact: {error}") from error


class PublisherState:
    def __init__(self, assets, directory, poll_seconds=60):
        self.assets = Path(assets).resolve()
        self.directory = Path(directory).resolve()
        self.lock = threading.RLock()
        self.current = None
        self.manifest = None
        self.posts = {}
        self.date_slugs = {}
        self.modes = []
        self.blog_ok = False
        self.modes_ok = False
        self.blog_success = 0.0
        self.modes_success = 0.0
        self.freshness = max(poll_seconds * 2, poll_seconds + API_TIMEOUT * 2)
        self.build = None
        self.rejected = None
        self.lease = None

    def load_current(self):
        """Pin verified data until every request using it has finished reading."""
        candidate = None
        lease = None
        try:
            # Transport holds EX while resolving current or retiring archives.
            # Development capture never retires archives and may have no lock.
            with contextlib.ExitStack() as publication:
                try:
                    promotion = publication.enter_context((self.directory / ".promotion.lock").open("rb"))
                except FileNotFoundError:
                    promotion = None
                if promotion is not None:
                    fcntl.flock(promotion, fcntl.LOCK_SH)
                with self.lock:
                    if self.build is None:
                        self.build = asset_fingerprint(self.assets)
                    link = self.directory / "current"
                    if not link.is_symlink():
                        return
                    candidate = link.resolve(strict=True)
                    if candidate.parent != self.directory or not re.fullmatch(r"release-[a-zA-Z0-9-]+", candidate.name):
                        raise PublisherError("Unsafe current artifact symlink")
                    if candidate in (self.current, self.rejected):
                        return
                    # Existing immutable manifest is readable on the RO mount;
                    # no serving-volume writes or lease files are needed.
                    lease = (candidate / MANIFEST).open("rb")
                    fcntl.flock(lease, fcntl.LOCK_SH)
                    manifest = validate_release(candidate, expected_build=self.build)
                    previous = self.lease
                    self.current = candidate
                    self.manifest = manifest
                    self.lease = lease
                    lease = None
                    self.rejected = None
                    if previous is not None:
                        previous.close()
        except (PublisherError, OSError) as error:
            with self.lock:
                if candidate is not None:
                    self.rejected = candidate
            print(f"[publisher-reader] Artifact rejected: {error}", flush=True)
        finally:
            if lease is not None:
                lease.close()

    def close(self):
        with self.lock:
            if self.lease is not None:
                self.lease.close()
                self.lease = None
            self.current = None
            self.manifest = None

    def available(self):
        return self.current is not None and self.manifest is not None and (self.assets / "spa-shell.html").is_file() and all(output_file(self.current, route).is_file() for route in STATIC_ROUTES)

    def dynamic_available(self, blog):
        success = self.blog_success if blog else self.modes_success
        ok = self.blog_ok if blog else self.modes_ok
        return ok and time.monotonic() - success <= self.freshness

    def route_status(self, route):
        if self.current is None or self.manifest is None:
            return 503
        item = self.manifest["routes"].get(route)
        if item is None or item["status"] != 200:
            return 503
        if route.startswith("/blog"):
            if not self.dynamic_available(True) or self.manifest["posts"]["status"] != 200:
                return 503
            if route.startswith("/blog/") and post_error(self.posts[route.removeprefix("/blog/")]):
                return 503
        if route == "/explore" and (not self.dynamic_available(False) or self.manifest["modes"]["status"] != 200):
            return 503
        return 200 if item["version"] == route_version(route, self.posts, self.modes, self.build) else 503


def refresh_blog(state, backend):
    try:
        posts = published_posts(backend)
        aliases = {}
        for slug, post in posts.items():
            try:
                puzzle_date = date.fromisoformat(post.get("date"))
                if puzzle_date.isoformat() == post["date"] and puzzle_date < datetime.now(timezone.utc).date():
                    aliases[post["date"]] = slug
            except (TypeError, ValueError):
                continue
        with state.lock:
            state.posts = posts
            state.date_slugs = aliases
            state.blog_ok = True
            state.blog_success = time.monotonic()
    except Exception as error:
        with state.lock:
            state.blog_ok = False
        print(f"[publisher-reader] Blog metadata unavailable: {error}", flush=True)


def refresh_modes(state, backend):
    try:
        modes = exploration_modes(backend)
        with state.lock:
            state.modes = modes
            state.modes_ok = True
            state.modes_success = time.monotonic()
    except Exception as error:
        with state.lock:
            state.modes_ok = False
        print(f"[publisher-reader] Explore metadata unavailable: {error}", flush=True)


def refresh(state, backend):
    state.load_current()
    refresh_blog(state, backend)
    refresh_modes(state, backend)


class PublisherServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, state):
        self.state = state
        super().__init__(address, PublisherHandler)


class PublisherHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_HEAD(self):
        self.do_GET()

    def respond(self, status, payload, content_type="text/html; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        if status == 503:
            self.send_header("X-Robots-Tag", "noindex, nofollow")
            self.send_header("Retry-After", "60")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def redirect(self, route):
        self.send_response(308)
        self.send_header("Location", route)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        state = self.server.state
        path = urllib.parse.urlsplit(self.path).path
        route = path.rstrip("/") or "/"
        decoded = urllib.parse.unquote(path).rstrip("/") or "/"
        if decoded != route and (decoded in ROUTES or decoded in GUIDE_ALIASES or decoded == "/blog" or decoded.startswith(("/blog/", "/explore/"))):
            self.respond(404, NOT_FOUND)
            return
        content_type = "text/html; charset=utf-8"
        with state.lock:
            if path == "/healthz":
                ready = state.available()
                self.respond(200 if ready else 503, b"ready\n" if ready else b"unavailable\n", "text/plain; charset=utf-8")
                return
            if route in GUIDE_ALIASES:
                self.redirect(GUIDE_ALIASES[route])
                return
            publisher = route in ROUTES or route == "/blog" or route.startswith("/blog/")
            if publisher:
                if route.startswith("/blog/"):
                    identifier = route.removeprefix("/blog/")
                    if not SLUG.fullmatch(identifier):
                        self.respond(404, NOT_FOUND)
                        return
                    try:
                        post_date = date.fromisoformat(identifier)
                    except ValueError:
                        post_date = None
                    if post_date is not None and post_date.isoformat() == identifier:
                        if post_date >= datetime.now(timezone.utc).date():
                            self.respond(404, NOT_FOUND)
                            return
                        slug = state.date_slugs.get(identifier)
                    else:
                        slug = identifier if identifier in state.posts else None
                    if not state.dynamic_available(True):
                        self.respond(503, UNAVAILABLE)
                        return
                    if slug is None:
                        self.respond(404, NOT_FOUND)
                        return
                    if slug != identifier:
                        self.redirect("/blog/" + slug)
                        return
                status = state.route_status(route)
                if status != 200:
                    self.respond(status, UNAVAILABLE)
                    return
                try:
                    payload = output_file(state.current, route).read_bytes()
                except OSError:
                    self.respond(503, UNAVAILABLE)
                    return
            else:
                # Nginx serves these in production; this also supports local HTTP smoke.
                candidate = (state.assets / urllib.parse.unquote(path).lstrip("/")).resolve()
                if not candidate.is_relative_to(state.assets) or any(part.startswith(".") for part in candidate.relative_to(state.assets).parts):
                    self.respond(404, b"Not found", "text/plain")
                    return
                if candidate.is_file() and candidate.name not in ("index.html", "spa-shell.html"):
                    try:
                        payload = candidate.read_bytes()
                    except OSError:
                        self.respond(503, UNAVAILABLE)
                        return
                    content_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
                elif path.startswith("/api/") or candidate.suffix or path.startswith("/explore/"):
                    self.respond(404, b"Not found", "text/plain")
                    return
                else:
                    try:
                        payload = (state.assets / "spa-shell.html").read_bytes()
                    except OSError:
                        self.respond(503, UNAVAILABLE)
                        return
        self.respond(200, payload, content_type)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("/var/run/countrydle-publisher"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--validate-release", type=Path)
    args = parser.parse_args()
    if args.validate_release is not None:
        validate_release(args.validate_release, args.assets_dir)
        print("[publisher-reader] Artifact validated", flush=True)
        return
    backend = backend_origin()
    interval = poll_interval()
    state = PublisherState(args.assets_dir or Path("/usr/share/nginx/html"), args.output_dir, interval)
    stop = threading.Event()
    state.load_current()
    server = PublisherServer(("127.0.0.1", args.port), state)

    def poll(function):
        while not stop.is_set():
            function(state, backend)
            stop.wait(interval)

    threads = [threading.Thread(target=server.serve_forever, daemon=True)]
    threads.extend(threading.Thread(target=poll, args=(function,), daemon=True) for function in (refresh_blog, refresh_modes))
    for thread in threads:
        thread.start()

    def shutdown(_signal, _frame):
        stop.set()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    try:
        # Artifact promotion is independent of potentially slow metadata requests.
        while not stop.wait(1):
            state.load_current()
    finally:
        stop.set()
        server.shutdown()
        server.server_close()
        for thread in threads:
            thread.join()
        state.close()


if __name__ == "__main__":
    try:
        main()
    except (PublisherError, OSError, ValueError) as error:
        raise SystemExit(f"[publisher-reader] Failed: {error}") from error
