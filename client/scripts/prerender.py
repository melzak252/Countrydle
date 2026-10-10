"""Real Chromium capture shared by the one-shot publisher worker.

Local use after a SPA build: PUBLISHER_BACKEND_URL=http://127.0.0.1:8080
python3 scripts/prerender.py. Output defaults to dist/publisher-snapshots/current;
the source SPA bundle is never replaced by captured HTML.
"""

import contextlib
from datetime import date, datetime, timezone
import http.server
import importlib
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

runtime = importlib.import_module("publisher-runtime")
CLIENT_DIR = Path(__file__).resolve().parent.parent


def configuration():
    backend = runtime.backend_origin()
    public = runtime.origin(os.environ.get("PUBLISHER_ORIGIN", "https://countrydle.online"))
    if urllib.parse.urlsplit(public).path:
        raise runtime.PublisherError("PUBLISHER_ORIGIN must not include a path")
    timeout = float(os.environ.get("PUBLISHER_CAPTURE_TIMEOUT", "45"))
    if not 5 <= timeout <= 300:
        raise runtime.PublisherError("PUBLISHER_CAPTURE_TIMEOUT must be between 5 and 300 seconds")
    return backend, public, timeout


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
            raise runtime.PublisherError("Missing Vite index.html; build the SPA first")
        text = source.read_text(encoding="utf-8")
        if re.search(r'<(?:main|article)\b', text, re.IGNORECASE):
            raise runtime.PublisherError("Cannot use a previously rendered homepage as the immutable SPA shell")
        atomic_write(shell, text)
    return shell


class CaptureServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, assets, backend, posts, modes=None):
        self.assets = assets.resolve()
        self.shell = shell_path(assets)
        self.backend = backend
        self.posts = posts
        self.modes = modes
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
                payload = runtime.fetch_bytes(self.server.backend + endpoint + ("?" + parsed.query if parsed.query else ""))
                data = json.loads(payload)
                if endpoint == "/explore/modes":
                    if not isinstance(data, list) or not data or data != self.server.modes:
                        raise runtime.PublisherError("Exploration modes changed or were malformed during capture")
                elif endpoint == "/blog":
                    if not isinstance(data, dict):
                        raise runtime.PublisherError("Captured blog response was malformed")
                    rows, total = data.get("posts"), data.get("total")
                    if not isinstance(rows, list) or type(total) is not int or total != len(self.server.posts):
                        raise runtime.PublisherError("Published blog changed during capture")
                    query = urllib.parse.parse_qs(parsed.query)
                    page = int(query.get("page", ["1"])[0])
                    limit = int(query.get("limit", ["10"])[0])
                    if page < 1 or not 1 <= limit <= 100:
                        raise runtime.PublisherError("Invalid capture blog pagination")
                    expected = list(self.server.posts.values())[(page - 1) * limit:page * limit]
                    if rows != expected:
                        raise runtime.PublisherError("Public blog versions changed during capture")
                else:
                    slug = endpoint.removeprefix("/blog/")
                    expected = self.server.posts[slug]
                    if not isinstance(data, dict) or any(data.get(key) != value for key, value in expected.items()):
                        raise runtime.PublisherError("Article version changed during capture")
                    related = runtime.related_dependencies(self.server.posts)[slug]
                    if data.get("related_posts") != related:
                        raise runtime.PublisherError("Related article metadata changed during capture")
                rows = data if isinstance(data, list) else data.get("posts", [data])
                today = datetime.now(timezone.utc).date()
                if any(date.fromisoformat(post["date"]) >= today for post in rows if "date" in post):
                    raise runtime.PublisherError("Capture API exposed today's or a future puzzle")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except Exception as error:
                self.server.failures.append(str(error))
                self.send_error(502, "Mandatory publisher API unavailable")
            return
        if path in runtime.ROUTES or path == "/blog" or path.removeprefix("/blog/") in self.server.posts:
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
            raise runtime.PublisherError("Install Python websocket-client for Chromium publisher capture") from error
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
                    raise runtime.PublisherError("Chromium publisher capture exceeded its readiness deadline")
                self.connection.settimeout(remaining)
            message = json.loads(self.connection.recv())
            if message.get("method") == "Fetch.requestPaused":
                paused = message["params"]
                allowed = self.allow_request and self.allow_request(paused["request"])
                self.send("Fetch.continueRequest" if allowed else "Fetch.failRequest", {"requestId": paused["requestId"], **({} if allowed else {"errorReason": "BlockedByClient"})})
            elif message.get("id") == request_id:
                if "error" in message:
                    raise runtime.PublisherError(f"Chromium {method} failed: {message['error']['message']}")
                return message.get("result", {})

    def close(self):
        self.connection.close()


class Browser:
    def __init__(self, timeout):
        executable = os.environ.get("CHROME_BIN")
        self.executable = shutil.which(executable) if executable else next((path for command in ("chromium-browser", "chromium", "google-chrome") if (path := shutil.which(command))), None)
        if not self.executable:
            raise runtime.PublisherError("Chromium is required; publisher capture cannot be skipped")
        self.timeout = timeout
        self.profile = tempfile.TemporaryDirectory(prefix="countrydle-chrome-")
        self.process = None
        self.connection = None
        self.stderr = None

    def private_environment(self):
        # Container --user UID:GID may have no passwd entry and inherit /root HOME.
        # Chromium/crashpad need writable per-user directories independently of
        # --user-data-dir; never rely on the image account or relax permissions.
        environment = os.environ.copy()
        root = Path(self.profile.name)
        for variable, directory in (
            ("HOME", "home"), ("XDG_CONFIG_HOME", "config"),
            ("XDG_CACHE_HOME", "cache"), ("XDG_DATA_HOME", "data"),
            ("XDG_RUNTIME_DIR", "runtime"),
        ):
            path = root / directory
            path.mkdir(mode=0o700)
            environment[variable] = str(path)
        return environment

    def launch_error(self, returncode):
        self.stderr.flush()
        self.stderr.seek(0, os.SEEK_END)
        self.stderr.seek(max(0, self.stderr.tell() - 4096))
        diagnostic = self.stderr.read(4096).decode("utf-8", errors="replace").strip()
        reason = f"exit {returncode}" if returncode is not None else "readiness deadline exceeded"
        return runtime.PublisherError(f"Chromium failed to become ready ({reason})" + (f": {diagnostic}" if diagnostic else ""))

    def __enter__(self):
        try:
            environment = self.private_environment()
            user_data = Path(self.profile.name) / "user-data"
            user_data.mkdir(mode=0o700)
            self.stderr = tempfile.TemporaryFile(dir=self.profile.name)
            self.process = subprocess.Popen([
                self.executable, "--headless=new", "--no-sandbox", "--disable-gpu",
                "--disable-background-networking", "--disable-component-update", "--disable-default-apps",
                "--disable-extensions", "--disable-sync", "--no-first-run", "--no-default-browser-check",
                "--metrics-recording-only", "--disable-domain-reliability", "--disable-quic",
                "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
                "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0",
                f"--user-data-dir={user_data}", "about:blank",
            ], env=environment, stdout=subprocess.DEVNULL, stderr=self.stderr, start_new_session=True)
            deadline = time.monotonic() + self.timeout
            active_port = user_data / "DevToolsActivePort"
            while not active_port.exists():
                returncode = self.process.poll()
                if returncode is not None or time.monotonic() >= deadline:
                    raise self.launch_error(returncode)
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
        if self.stderr:
            self.stderr.close()
        self.profile.cleanup()

    def capture(self, server, route, public_origin):
        server.failures.clear()
        context_id = self.connection.call("Target.createBrowserContext")["browserContextId"]
        page = None
        try:
            target_id = self.connection.call("Target.createTarget", {"url": "about:blank", "browserContextId": context_id})["targetId"]
            targets = json.loads(runtime.fetch_bytes(self.debug_url + "/json/list"))
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
                    raise runtime.PublisherError(f"Mandatory content failed while capturing {route}")
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
                        post_meta = server.posts[route.removeprefix("/blog/")]
                        valid = valid and (post_meta["title"] in state.get("heading", "") or post_meta.get("country_name", "") in state.get("heading", ""))
                signature = json.dumps(state, sort_keys=True)
                if valid and signature == previous:
                    if stable_since is not None and time.monotonic() - stable_since >= 0.5:
                        break
                else:
                    stable_since = time.monotonic() if valid else None
                previous = signature
                time.sleep(0.1)
            else:
                raise runtime.PublisherError(f"Mandatory heading, metadata or loaded content never became ready: {route}")
            html = page.call("Runtime.evaluate", {"expression": """(() => {
                const clone = document.documentElement.cloneNode(true);
                clone.querySelectorAll('noscript, [data-prerender-remove]').forEach(node => node.remove());
                clone.style.removeProperty('--app-height');
                return '<!doctype html>\\n' + clone.outerHTML;
            })()""", "returnByValue": True})["result"]["value"]
            # Local capture origin may appear only in browser-resolved metadata.
            html = html.replace(capture_origin, public_origin).replace("https://countrydle.online", public_origin)
            if re.search(r"(?:localhost|127\.0\.0\.1|__COUNTRYDLE_PRERENDER__|<iframe\b|<ins\b[^>]*adsbygoogle|<script\b[^>]*src=[\"']https?://(?!www\.googletagmanager\.com/))", html, re.IGNORECASE):
                raise runtime.PublisherError(f"Unsafe publisher runtime or loopback artifacts in {route}")
            return html
        finally:
            if page:
                page.close()
            self.connection.call("Target.disposeBrowserContext", {"browserContextId": context_id})


@contextlib.contextmanager
def capture_session(assets, backend, posts, timeout, modes=None):
    server = CaptureServer(assets, backend, posts, modes)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with Browser(timeout) as browser:
            yield server, browser
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def prerender():
    # Preserve publisher:build as the same real one-shot capture entrypoint.
    importlib.import_module("publisher-capture").main(default_assets=CLIENT_DIR / "dist")


if __name__ == "__main__":
    try:
        prerender()
    except Exception as error:
        raise SystemExit(f"[publisher] Failed: {error}") from error
