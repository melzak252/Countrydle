"""Capture real public React pages; never substitute a failed API with empty data.

Local use: build the SPA, install Chromium and Python websocket-client, then run
PUBLISHER_BACKEND_URL=http://127.0.0.1:8080 python3 scripts/prerender.py.
The container uses the same capture implementation from publisher-runtime.py.
"""

import argparse
import contextlib
from datetime import date, datetime, timezone
import hashlib
import http.server
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import urllib.parse
import urllib.request

CLIENT_DIR = Path(__file__).resolve().parent.parent
ROUTES = (
    "/", "/about", "/how-it-works", "/faq", "/explore",
    "/explore/modes/countrydle", "/explore/modes/us-states",
    "/explore/modes/wojewodztwa", "/explore/modes/powiaty",
    "/explore/modes/flagdle", "/explore/modes/europe",
    "/explore/modes/asia", "/explore/modes/africa", "/explore/modes/americas",
    "/privacy-policy", "/terms", "/cookie-policy", "/contact",
)
GUIDE_ALIASES = {"/explore/modes/us_statedle": "/explore/modes/us-states"}
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
API_TIMEOUT = 10


class PublisherError(RuntimeError):
    pass


def origin(value):
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise PublisherError("Publisher origins must be absolute HTTP(S) URLs without credentials, query or fragment")
    return value.rstrip("/")


def configuration():
    backend = origin(os.environ.get("PUBLISHER_BACKEND_URL", "http://backend:8080"))
    public = origin(os.environ.get("PUBLISHER_ORIGIN", "https://countrydle.online"))
    if urllib.parse.urlsplit(public).path:
        raise PublisherError("PUBLISHER_ORIGIN must not include a path")
    timeout = float(os.environ.get("PUBLISHER_CAPTURE_TIMEOUT", "45"))
    if not 5 <= timeout <= 300:
        raise PublisherError("PUBLISHER_CAPTURE_TIMEOUT must be between 5 and 300 seconds")
    return backend, public, timeout


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def fetch_bytes(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Countrydle-Publisher/1", "Accept": "application/json"})
    # Do not inherit proxy credentials, cookies, or authorization from the host.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=API_TIMEOUT) as response:
        if response.status != 200 or response.headers.get_content_type() != "application/json":
            raise PublisherError("Mandatory public API did not return JSON with HTTP 200")
        return response.read()


def published_posts(backend):
    posts = {}
    total = None
    page = 1
    today = datetime.now(timezone.utc).date()
    while total is None or len(posts) < total:
        payload = json.loads(fetch_bytes(f"{backend}/blog?page={page}&limit=50"))
        rows = payload.get("posts")
        count = payload.get("total")
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
            slug = post.get("slug", "")
            if not isinstance(slug, str) or not SLUG.fullmatch(slug) or slug in posts:
                raise PublisherError("Published blog contains an unsafe or duplicate slug")
            if date.fromisoformat(post["date"]) >= today:
                raise PublisherError("Public API exposed today's or a future puzzle")
            if not post.get("title") or not post.get("summary") or not (post.get("updated_at") or post.get("created_at")):
                raise PublisherError("Published blog metadata is incomplete")
            posts[slug] = post
        if len(posts) > total:
            raise PublisherError("Published blog total disagrees with its results")
        page += 1
    return posts


def exploration_modes(backend):
    modes = json.loads(fetch_bytes(f"{backend}/explore/modes"))
    if not isinstance(modes, list) or not modes or any(not isinstance(mode, dict) for mode in modes):
        raise PublisherError("Mandatory exploration modes returned empty or malformed data")
    return modes


def fingerprint(posts):
    return hashlib.sha256(json.dumps(posts, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".publisher-", delete=False) as temporary:
        name = temporary.name
        try:
            temporary.write(content.encode("utf-8"))
            temporary.flush()
            os.fsync(temporary.fileno())
        except BaseException:
            os.unlink(name)
            raise
    try:
        os.chmod(name, 0o644)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def shell_path(assets):
    shell = assets / "spa-shell.html"
    if not shell.exists():
        source = assets / "index.html"
        if not source.is_file():
            raise PublisherError("Missing Vite index.html; build the SPA first")
        text = source.read_text(encoding="utf-8")
        if re.search(r'<(?:main|article)\b', text, re.IGNORECASE):
            raise PublisherError("Cannot use a previously rendered homepage as the immutable SPA shell")
        atomic_write(shell, text)
    return shell


class CaptureServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, assets, backend, posts):
        self.assets = assets.resolve()
        self.shell = shell_path(assets)
        self.backend = backend
        self.posts = posts
        self.failures = []
        super().__init__(("127.0.0.1", 0), CaptureHandler)


class CaptureHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(args[2].assets), **kwargs)

    def log_message(self, *_args):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        if path.startswith("/api/"):
            endpoint = path[4:]
            if endpoint not in ("/blog", "/explore/modes") and endpoint.removeprefix("/blog/") not in self.server.posts:
                self.send_error(403)
                return
            try:
                payload = fetch_bytes(self.server.backend + endpoint + ("?" + parsed.query if parsed.query else ""))
                data = json.loads(payload)
                if endpoint == "/explore/modes":
                    if not isinstance(data, list) or not data:
                        raise PublisherError("Mandatory exploration modes were empty or malformed")
                else:
                    if endpoint == "/blog":
                        rows = data.get("posts")
                        total = data.get("total")
                        if not isinstance(rows, list) or type(total) is not int or total < 0 or (not rows and total > 0) or (total == 0 and rows):
                            raise PublisherError("Captured blog response was malformed or falsely empty")
                        if (total == 0) != (not self.server.posts):
                            raise PublisherError("Published blog changed during capture")
                    else:
                        rows = [data]
                    today = datetime.now(timezone.utc).date()
                    if any(date.fromisoformat(post["date"]) >= today for post in rows):
                        raise PublisherError("Capture API exposed today's or a future puzzle")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except Exception as error:
                self.server.failures.append(str(error))
                self.send_error(502, "Mandatory publisher API unavailable")
            return
        if path in ROUTES or path == "/blog" or path.removeprefix("/blog/") in self.server.posts:
            data = self.server.shell.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path == "/spa-shell.html" or not (self.server.assets / path.lstrip("/")).resolve().is_relative_to(self.server.assets):
            self.send_error(404)
            return
        super().do_GET()


class DevTools:
    def __init__(self, url, timeout):
        try:
            import websocket
        except ImportError as error:
            raise PublisherError("Install Python websocket-client for Chromium publisher capture") from error
        self.connection = websocket.create_connection(url, timeout=timeout, suppress_origin=True, http_no_proxy=["127.0.0.1", "localhost"])
        self.sequence = 0
        self.allow_request = None
        self.deadline = None

    def send(self, method, params=None):
        self.sequence += 1
        self.connection.send(json.dumps({"id": self.sequence, "method": method, "params": params or {}}))
        return self.sequence

    def call(self, method, params=None):
        request_id = self.send(method, params)
        while True:
            if self.deadline is not None:
                remaining = self.deadline - time.monotonic()
                if remaining <= 0:
                    raise PublisherError("Chromium publisher capture exceeded its readiness deadline")
                self.connection.settimeout(remaining)
            message = json.loads(self.connection.recv())
            if message.get("method") == "Fetch.requestPaused":
                paused = message["params"]
                allowed = self.allow_request and self.allow_request(paused["request"])
                self.send("Fetch.continueRequest" if allowed else "Fetch.failRequest", {"requestId": paused["requestId"], **({} if allowed else {"errorReason": "BlockedByClient"})})
            elif message.get("id") == request_id:
                if "error" in message:
                    raise PublisherError(f"Chromium {method} failed: {message['error']['message']}")
                return message.get("result", {})

    def close(self):
        self.connection.close()


class Browser:
    def __init__(self, timeout):
        executable = os.environ.get("CHROME_BIN")
        self.executable = shutil.which(executable) if executable else next((path for command in ("chromium-browser", "chromium", "google-chrome") if (path := shutil.which(command))), None)
        if not self.executable:
            raise PublisherError("Chromium is required; publisher capture cannot be skipped")
        self.timeout = timeout
        self.profile = tempfile.TemporaryDirectory(prefix="countrydle-chrome-")
        self.process = None
        self.connection = None

    def __enter__(self):
        self.process = subprocess.Popen([
            self.executable, "--headless=new", "--no-sandbox", "--disable-gpu",
            "--disable-background-networking", "--disable-component-update", "--disable-default-apps",
            "--disable-extensions", "--disable-sync", "--no-first-run", "--no-default-browser-check",
            "--metrics-recording-only", "--disable-domain-reliability", "--disable-quic",
            "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
            "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0",
            f"--user-data-dir={self.profile.name}", "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            deadline = time.monotonic() + self.timeout
            active_port = Path(self.profile.name) / "DevToolsActivePort"
            while not active_port.exists():
                if self.process.poll() is not None or time.monotonic() >= deadline:
                    raise PublisherError("Chromium failed to become ready")
                time.sleep(0.05)
            port, endpoint = active_port.read_text().splitlines()[:2]
            self.debug_url = f"http://127.0.0.1:{port}"
            self.connection = DevTools(f"ws://127.0.0.1:{port}{endpoint}", self.timeout)
            self.connection.call("Browser.getVersion")
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_args):
        if self.connection:
            self.connection.close()
        if self.process and self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait()
        self.profile.cleanup()

    def capture(self, server, route, public_origin):
        context_id = self.connection.call("Target.createBrowserContext")["browserContextId"]
        page = None
        try:
            target_id = self.connection.call("Target.createTarget", {"url": "about:blank", "browserContextId": context_id})["targetId"]
            targets = json.loads(fetch_bytes(self.debug_url + "/json/list"))
            target = next(target for target in targets if target["id"] == target_id)
            page = DevTools(target["webSocketDebuggerUrl"], self.timeout)
            capture_origin = f"http://127.0.0.1:{server.server_port}"

            def permitted(request):
                parsed = urllib.parse.urlsplit(request["url"])
                if request["method"] != "GET" or f"{parsed.scheme}://{parsed.netloc}" != capture_origin:
                    return False
                if parsed.path.startswith("/api/"):
                    return parsed.path in ("/api/blog", "/api/explore/modes") or parsed.path.removeprefix("/api/blog/") in server.posts
                return parsed.path == route or parsed.path.startswith(("/assets/", "/fonts/", "/images/")) or parsed.path in ("/favicon.ico", "/favicon.svg", "/logo.svg")

            page.allow_request = permitted
            page.call("Page.enable")
            page.call("Runtime.enable")
            page.call("Fetch.enable", {"patterns": [{"urlPattern": "*", "requestStage": "Request"}]})
            page.call("Page.addScriptToEvaluateOnNewDocument", {"source": "Object.defineProperty(window, '__COUNTRYDLE_PRERENDER__', {value: true, configurable: true});"})
            page.deadline = time.monotonic() + self.timeout
            page.call("Page.navigate", {"url": capture_origin + route})
            deadline = page.deadline
            previous = None
            stable_since = None
            while time.monotonic() < deadline:
                result = page.call("Runtime.evaluate", {"expression": """(() => {
                    const main = document.querySelector('main');
                    return {path: location.pathname, title: document.title,
                        text: main?.textContent?.trim() || '', heading: main?.querySelector('h1')?.textContent?.trim() || '',
                        description: document.querySelector('meta[name="description"]')?.content || '',
                        canonical: document.querySelector('link[rel="canonical"]')?.href || '',
                        ogUrl: document.querySelector('meta[property="og:url"]')?.content || '',
                        robots: document.querySelector('meta[name="robots"]')?.content || '',
                        schema: !!document.querySelector('script#countrydle-page-schema[type="application/ld+json"]'),
                        ready: !!main?.querySelector('[data-publisher-ready="true"]'),
                        error: !!document.querySelector('[data-publisher-error="true"]'),
                        content: main?.querySelectorAll('p, li').length || 0,
                        links: [...(main?.querySelectorAll('a[href]') || [])].map(a => a.getAttribute('href'))};
                })()""", "returnByValue": True})
                state = result.get("result", {}).get("value", {})
                if state.get("error") or server.failures:
                    raise PublisherError(f"Mandatory content failed while capturing {route}")
                valid = state.get("path") == route and state.get("heading") and len(state.get("text", "")) >= 160 and state.get("content", 0) >= 2 and state.get("title") and state.get("description") and state.get("canonical")
                canonical_path = urllib.parse.urlsplit(state.get("canonical", "")).path or "/"
                metadata = canonical_path == route and state.get("canonical") == state.get("ogUrl")
                empty_blog = route == "/blog" and not server.posts
                indexable = state.get("schema") and "index" in state.get("robots", "") and "noindex" not in state.get("robots", "")
                valid = valid and metadata and (("noindex" in state.get("robots", "")) if empty_blog else indexable)
                if route == "/explore" or route.startswith("/blog"):
                    valid = valid and state.get("ready")
                    if route == "/blog":
                        valid = valid and (empty_blog or any(link == "/blog/" + slug for link in state.get("links", []) for slug in server.posts))
                    elif route.startswith("/blog/"):
                        valid = valid and server.posts[route.removeprefix("/blog/")]["title"] in state.get("heading", "")
                signature = json.dumps(state, sort_keys=True)
                if valid and signature == previous:
                    if stable_since is not None and time.monotonic() - stable_since >= 0.5:
                        break
                else:
                    stable_since = time.monotonic() if valid else None
                previous = signature
                time.sleep(0.1)
            else:
                raise PublisherError(f"Mandatory heading, metadata or loaded content never became ready: {route}")
            html = page.call("Runtime.evaluate", {"expression": """(() => {
                const clone = document.documentElement.cloneNode(true);
                clone.querySelectorAll('noscript, [data-prerender-remove]').forEach(node => node.remove());
                clone.style.removeProperty('--app-height');
                return '<!doctype html>\\n' + clone.outerHTML;
            })()""", "returnByValue": True})["result"]["value"]
            # Local capture origin may appear only in browser-resolved metadata.
            html = html.replace(capture_origin, public_origin).replace("https://countrydle.online", public_origin)
            if re.search(r"(?:localhost|127\.0\.0\.1|__COUNTRYDLE_PRERENDER__|<iframe\b|<ins\b[^>]*adsbygoogle|<script\b[^>]*src=[\"']https?://)", html, re.IGNORECASE):
                raise PublisherError(f"Unsafe publisher runtime or loopback artifacts in {route}")
            return html
        finally:
            if page:
                page.close()
            self.connection.call("Target.disposeBrowserContext", {"browserContextId": context_id})


@contextlib.contextmanager
def capture_session(assets, backend, posts, timeout):
    server = CaptureServer(assets, backend, posts)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with Browser(timeout) as browser:
            yield server, browser
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def output_file(directory, route):
    return directory / route.lstrip("/") / "index.html"


def prerender():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets-dir", type=Path, default=CLIENT_DIR / "dist")
    parser.add_argument("--output-dir", type=Path, help="Defaults to the built dist directory")
    args = parser.parse_args()
    backend, public_origin, timeout = configuration()
    posts = published_posts(backend)
    modes = exploration_modes(backend)
    output = args.output_dir or args.assets_dir
    with tempfile.TemporaryDirectory(prefix="countrydle-publisher-") as temporary:
        staging = Path(temporary)
        with capture_session(args.assets_dir, backend, posts, timeout) as (server, browser):
            for route in (*ROUTES, "/blog", *("/blog/" + slug for slug in posts)):
                atomic_write(output_file(staging, route), browser.capture(server, route, public_origin))
        if fingerprint(published_posts(backend)) != fingerprint(posts):
            raise PublisherError("Public posts changed during capture; no output was published")
        if fingerprint(exploration_modes(backend)) != fingerprint(modes):
            raise PublisherError("Public exploration modes changed during capture; no output was published")
        for route in (*ROUTES, "/blog", *("/blog/" + slug for slug in posts)):
            atomic_write(output_file(output, route), output_file(staging, route).read_text(encoding="utf-8"))
        # Remove only obsolete snapshots owned by this publisher, never SPA assets.
        manifest_path = output / ".publisher-posts.json"
        if manifest_path.exists():
            previous = json.loads(manifest_path.read_text())
            for slug in previous.keys() - posts.keys():
                if SLUG.fullmatch(slug):
                    obsolete = output_file(output, "/blog/" + slug)
                    if obsolete.exists():
                        obsolete.unlink()
        atomic_write(manifest_path, json.dumps(posts, sort_keys=True))
    print(f"[publisher] Published {len(ROUTES) + 1 + len(posts)} validated public snapshots")


if __name__ == "__main__":
    try:
        prerender()
    except Exception as error:
        raise SystemExit(f"[publisher] Failed: {error}") from error
