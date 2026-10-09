"""Read-only public-content refresh and readiness server behind frontend nginx."""

import argparse
import fcntl
import http.server
from datetime import date, datetime, timezone
import json
import mimetypes
import os
from itertools import islice
from pathlib import Path
import shutil
import signal
import threading
import time
import urllib.parse
import uuid

from prerender import (
    API_TIMEOUT, GUIDE_ALIASES, ROUTES, PublisherError, atomic_write, capture_session,
    configuration, exploration_modes, fingerprint, output_file, published_posts, shell_path,
)

UNAVAILABLE = b'<!doctype html><html lang="en"><head><meta name="robots" content="noindex"><title>Countrydle temporarily unavailable</title></head><body><h1>Publisher content temporarily unavailable</h1><p>Please try again shortly.</p></body></html>'


class PublisherState:
    def __init__(self, assets, directory, poll_seconds, timeout):
        self.assets = assets.resolve()
        self.directory = directory.resolve()
        self.lock = threading.Lock()
        self.ready = False
        self.current = None
        self.posts = {}
        self.date_slugs = {}
        self.modes = None
        self.last_success = 0.0
        self.freshness = max(poll_seconds * 2, timeout + poll_seconds + API_TIMEOUT)

    def available(self):
        return self.ready and self.current is not None and time.monotonic() - self.last_success <= self.freshness

    def unavailable(self):
        with self.lock:
            self.ready = False

    def publish(self, staging, posts, modes):
        release = self.directory / ("release-" + uuid.uuid4().hex)
        staging.rename(release)
        temporary_link = self.directory / (".current-" + uuid.uuid4().hex)
        temporary_link.symlink_to(release.name, target_is_directory=True)
        with self.lock:
            os.replace(temporary_link, self.directory / "current")
            previous = self.current
            self.current = release
            self.posts = posts
            self.date_slugs = {post["date"]: slug for slug, post in posts.items()}
            self.modes = modes
            self.last_success = time.monotonic()
            self.ready = True
        if previous is not None:
            shutil.rmtree(previous)


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
        # Never turn malformed, encoded, or nested blog URLs into a SPA success.
        publisher = route in ROUTES or route in GUIDE_ALIASES or route == "/blog" or route.startswith("/blog/")
        with state.lock:
            if path == "/healthz":
                self.respond(200 if state.available() else 503, b"ready\n" if state.available() else b"unavailable\n", "text/plain; charset=utf-8")
                return
            if publisher:
                if not state.available():
                    self.respond(503, UNAVAILABLE)
                    return
                if route in GUIDE_ALIASES:
                    self.redirect(GUIDE_ALIASES[route])
                    return
                if route.startswith("/blog/"):
                    identifier = route.removeprefix("/blog/")
                    try:
                        post_date = date.fromisoformat(identifier)
                    except ValueError:
                        post_date = None
                    if post_date is not None and post_date.isoformat() == identifier:
                        slug = state.date_slugs.get(identifier) if post_date < datetime.now(timezone.utc).date() else None
                        if slug is not None and slug != identifier:
                            self.redirect("/blog/" + slug)
                            return
                    else:
                        slug = identifier if identifier in state.posts else None
                    if slug is None:
                        self.respond(404, b"<!doctype html><title>Recap not found</title><h1>Recap not found</h1>")
                        return
                file = output_file(state.current, route)
                try:
                    payload = file.read_bytes()
                except OSError:
                    state.ready = False
                    self.respond(503, UNAVAILABLE)
                    return
            else:
                # Also usable as a local server; nginx normally serves these assets.
                candidate = (state.assets / urllib.parse.unquote(path).lstrip("/")).resolve()
                if not candidate.is_relative_to(state.assets) or candidate.name.startswith("."):
                    self.respond(404, b"Not found", "text/plain")
                    return
                if candidate.is_file() and candidate.name not in ("index.html", "spa-shell.html"):
                    payload = candidate.read_bytes()
                    content_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
                    self.respond(200, payload, content_type)
                    return
                if path.startswith("/api/") or candidate.suffix:
                    self.respond(404, b"Not found", "text/plain")
                    return
                payload = (state.assets / "spa-shell.html").read_bytes()
        self.respond(200, payload)


def related_dependencies(posts):
    """Mirror public detail: first four list results, exclude own ID, take three."""
    recent = list(islice(posts.values(), 4))
    return {
        slug: [candidate for candidate in recent if candidate["id"] != post["id"]][:3]
        for slug, post in posts.items()
    }


def refresh(state, backend, public_origin, timeout):
    posts = published_posts(backend)
    modes = exploration_modes(backend)
    with state.lock:
        previous_posts = state.posts
        previous_modes = state.modes
        previous_release = state.current
    dependencies = related_dependencies(posts)
    previous_dependencies = related_dependencies(previous_posts)
    if previous_release is not None and posts == previous_posts and modes == previous_modes and dependencies == previous_dependencies:
        required = (*ROUTES, "/blog", *("/blog/" + slug for slug in posts))
        if any(not output_file(previous_release, route).is_file() for route in required):
            raise PublisherError("An immutable publisher snapshot is missing; restart the publisher to regenerate")
        with state.lock:
            state.last_success = time.monotonic()
            state.ready = True
        return
    # Updated/reviewed/deleted content must not leave stale publisher HTML eligible.
    state.unavailable()
    staging = state.directory / (".next-" + uuid.uuid4().hex)
    try:
        if previous_release is None:
            staging.mkdir()
            routes = list(ROUTES)
        else:
            shutil.copytree(previous_release, staging, copy_function=os.link)
            routes = []
            if modes != previous_modes:
                routes.append("/explore")
        if previous_release is None or posts != previous_posts:
            routes.append("/blog")
        for slug, post in posts.items():
            if previous_posts.get(slug) != post or previous_dependencies.get(slug) != dependencies[slug]:
                routes.append("/blog/" + slug)
        for slug in previous_posts.keys() - posts.keys():
            shutil.rmtree(staging / "blog" / slug)
        with capture_session(state.assets, backend, posts, timeout) as (server, browser):
            for route in routes:
                atomic_write(output_file(staging, route), browser.capture(server, route, public_origin))
        if fingerprint(published_posts(backend)) != fingerprint(posts):
            raise PublisherError("Public posts changed during capture; retaining unavailable state until next poll")
        if fingerprint(exploration_modes(backend)) != fingerprint(modes):
            raise PublisherError("Public exploration modes changed during capture; retaining unavailable state until next poll")
        atomic_write(staging / ".publisher-posts.json", json.dumps(posts, sort_keys=True))
        state.publish(staging, posts, modes)
        print(f"[publisher] Published {len(routes)} changed routes ({len(posts)} public posts)", flush=True)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets-dir", type=Path, default=Path("/usr/share/nginx/html"))
    parser.add_argument("--output-dir", type=Path, default=Path("/var/run/countrydle-publisher"))
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    backend, public_origin, timeout = configuration()
    poll_seconds = float(os.environ.get("PUBLISHER_POLL_SECONDS", "60"))
    if not 5 <= poll_seconds <= 3600:
        raise PublisherError("PUBLISHER_POLL_SECONDS must be between 5 and 3600 seconds")
    shell_path(args.assets_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    # A second publisher must never race the current symlink or delete its release.
    with (args.output_dir / ".publisher.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for child in args.output_dir.iterdir():
            if child.name.startswith(("release-", ".next-")) and child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            elif child.name == "current" or child.name.startswith(".current-"):
                if child.is_symlink():
                    child.unlink()
        state = PublisherState(args.assets_dir, args.output_dir, poll_seconds, timeout)
        server = PublisherServer(("127.0.0.1", args.port), state)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        stop = threading.Event()

        def shutdown(_signal, _frame):
            stop.set()
            raise KeyboardInterrupt

        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)
        try:
            while not stop.is_set():
                try:
                    refresh(state, backend, public_origin, timeout)
                except Exception as error:
                    state.unavailable()
                    # Log diagnostics, never include backend exceptions in public HTML.
                    print(f"[publisher] Unavailable: {error}", flush=True)
                stop.wait(poll_seconds)
        except KeyboardInterrupt:
            pass
        finally:
            state.unavailable()
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    main()
