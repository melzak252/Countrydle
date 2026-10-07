import ctypes
import http.server
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

CLIENT_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = CLIENT_DIR / "dist"

ROUTES = [
    "/about",
    "/how-it-works",
    "/faq",
    "/explore",
    "/explore/modes/countrydle",
    "/explore/modes/us-states",
    "/explore/modes/wojewodztwa",
    "/explore/modes/powiaty",
    "/privacy-policy",
    "/terms",
    "/cookie-policy",
    "/contact",
    "/patch-notes",
    "/archive",
    "/leaderboard",
    "/border-hop",
]


def get_api_target() -> str | None:
    target = os.environ.get("PRERENDER_API_TARGET") or os.environ.get("API_PROXY_TARGET")
    static_only = os.environ.get("PRERENDER_STATIC_ONLY", "0")
    if static_only not in {"0", "1"}:
        raise ValueError("PRERENDER_STATIC_ONLY must be 0 or 1.")
    if static_only == "1":
        if target:
            raise ValueError("Choose either PRERENDER_STATIC_ONLY=1 or a configured backend target, not both.")
        return None
    if not target:
        raise ValueError("Set PRERENDER_API_TARGET to the matching local backend origin (or explicitly set PRERENDER_STATIC_ONLY=1).")
    parsed = urllib.parse.urlsplit(target)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username or parsed.password or parsed.path not in {"", "/"}
            or parsed.query or parsed.fragment):
        raise ValueError("PRERENDER_API_TARGET must be a local HTTP origin, without credentials or an API path.")
    return target.rstrip("/")


# Do not follow a backend redirect into an unrelated service or external provider.
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


BACKEND_HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())


def get_dynamic_routes(api_target: str) -> list[str]:
    req = urllib.request.Request(f"{api_target}/blog?limit=50", headers={"User-Agent": "Prerender"})
    with BACKEND_HTTP.open(req, timeout=5) as resp:
        data = json.load(resp)
    routes = ["/blog"]
    for post in data["posts"]:
        slug = post["slug"]
        if not isinstance(slug, str) or not slug or "/" in slug or slug in {".", ".."}:
            raise ValueError(f"Invalid blog slug: {slug!r}")
        routes.append(f"/blog/{urllib.parse.quote(slug, safe='')}")
    return routes


class SnapshotServer(http.server.ThreadingHTTPServer):
    # A pending backend GET must not serialize JS/CSS delivery or other API GETs.
    daemon_threads = False

    def __init__(self, *args, **kwargs):
        self.api_target = ""
        self.request_errors = []
        self.error_lock = threading.Lock()
        self.requests_idle = threading.Condition(self.error_lock)
        self.active_requests = 0
        super().__init__(*args, **kwargs)

    def record_error(self, message):
        with self.error_lock:
            self.request_errors.append(message)

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(5)
        return connection, address

    def process_request(self, request, client_address):
        with self.requests_idle:
            self.active_requests += 1
        super().process_request(request, client_address)

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            with self.requests_idle:
                self.active_requests -= 1
                self.requests_idle.notify_all()

    def wait_for_requests(self):
        with self.requests_idle:
            if not self.requests_idle.wait_for(lambda: self.active_requests == 0, timeout=5):
                raise RuntimeError("Snapshot server still has pending requests after browser cleanup")


class SPAHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST_DIR), **kwargs)

    def do_GET(self):
        # Chrome uses this server as a rejecting proxy for ALL non-loopback traffic.
        # Ads, analytics and background browser services cannot delay rendering or
        # contact providers; local assets and /api GETs bypass that browser proxy.
        if urllib.parse.urlsplit(self.path).netloc:
            self.send_error(403, "External network disabled during prerender")
            return
        if self.path.startswith("/api/"):
            if not self.server.api_target:
                self.send_error(503, "Backend unavailable in explicit static-only prerender mode")
                return
            target_url = f"{self.server.api_target}/{self.path[5:]}"
            try:
                req = urllib.request.Request(target_url, headers={"User-Agent": "Prerender"})
                with BACKEND_HTTP.open(req, timeout=5) as resp:
                    body = resp.read()
                    self.send_response(resp.status)
                    self.send_header("Content-Type", resp.headers.get("Content-Type", "application/json"))
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                self.server.record_error(f"{self.path}: {exc}")
                self.send_error(502, "Configured backend GET failed")
            return
        path = self.translate_path(self.path)
        if not Path(path).exists() or Path(path).is_dir():
            self.path = "/index.html"
        super().do_GET()

    def do_CONNECT(self):
        self.send_error(403, "External network disabled during prerender")

    def log_message(self, *args):
        pass


def find_chrome() -> str | None:
    if os.environ.get("CHROME_BIN"):
        return shutil.which(os.environ["CHROME_BIN"])
    for cmd in ["google-chrome", "chromium-browser", "chromium"]:
        which = shutil.which(cmd)
        if which:
            return which
    return None


def cleanup_browser(process: subprocess.Popen, profile_root: Path):
    # Crashpad can detach into a separate session. Match only this invocation's
    # private profile/config directory, never arbitrary system Chrome processes.
    owned = set()
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            group = int((entry / "stat").read_text().rsplit(") ", 1)[1].split()[2])
            command = (entry / "cmdline").read_bytes().decode("utf-8", errors="replace")
            if group == process.pid or f"{profile_root}/" in command:
                owned.add(int(entry.name))
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    for pid in owned - {process.pid}:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=1)
    # Adopt/reap orphaned descendants rather than leaving zombies after a timeout.
    pending = owned - {process.pid}
    deadline = time.monotonic() + 1
    while pending and time.monotonic() < deadline:
        for pid in list(pending):
            try:
                if os.waitpid(pid, os.WNOHANG)[0]:
                    pending.remove(pid)
            except ChildProcessError:
                if not Path(f"/proc/{pid}").exists():
                    pending.remove(pid)
        if pending:
            time.sleep(0.01)


class RenderedRoot(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_root = False
        self.populated = False

    def handle_starttag(self, tag, attrs):
        if self.in_root:
            self.populated = True
        elif tag == "div" and ("id", "root") in attrs:
            self.in_root = True

    def handle_endtag(self, tag):
        if tag == "div":
            self.in_root = False

    def handle_data(self, data):
        if self.in_root and data.strip():
            self.populated = True


def render_route(chrome_bin: str, url: str, timeout: float = 15) -> str:
    if not sys.platform.startswith("linux"):
        raise RuntimeError("Prerender requires Linux (the supported frontend container runtime).")
    # PR_SET_CHILD_SUBREAPER: reap even double-forked browser helpers we own.
    if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "Could not enable browser descendant cleanup")
    with tempfile.TemporaryDirectory(prefix="countrydle-prerender-") as directory:
        profile_root = Path(directory)
        env = dict(os.environ, XDG_CONFIG_HOME=str(profile_root / "config"), XDG_CACHE_HOME=str(profile_root / "cache"))
        origin = urllib.parse.urlsplit(url).netloc
        args = [
            chrome_bin,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-component-update",
            "--disable-breakpad",
            "--disable-crash-reporter",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-quic",
            f"--user-data-dir={profile_root / 'profile'}",
            f"--proxy-server=http://{origin}",
            f"--proxy-bypass-list=<-loopback>;{origin}",
            "--virtual-time-budget=2000",
            "--dump-dom",
            url,
        ]
        # Files avoid inherited pipe handles keeping communicate() alive after the
        # browser exits. The fixed deadline covers the entire browser invocation.
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            process = subprocess.Popen(args, stdout=stdout, stderr=stderr, env=env, start_new_session=True)
            try:
                process.wait(timeout=timeout)
                if process.returncode:
                    stderr.seek(0)
                    raise RuntimeError(f"Chrome exited {process.returncode}: {stderr.read().decode('utf-8', errors='replace')}")
                stdout.seek(0)
                html = stdout.read().decode("utf-8")
                if "<html" not in html.lower() or "</html>" not in html.lower():
                    raise RuntimeError("Chrome did not produce a complete HTML document")
                root = RenderedRoot()
                root.feed(html)
                if not root.populated:
                    raise RuntimeError("Chrome returned HTML without a rendered application root")
                return html
            finally:
                cleanup_browser(process, profile_root)


def prerender() -> int:
    try:
        api_target = get_api_target()
        if not (DIST_DIR / "index.html").exists():
            raise ValueError(f"{DIST_DIR / 'index.html'} does not exist. Run 'vite build' first.")
        chrome_bin = find_chrome()
        if not chrome_bin:
            raise ValueError("Chrome/Chromium not found. Install it or set CHROME_BIN.")
        dynamic_routes = get_dynamic_routes(api_target) if api_target else ["/blog"]
        all_routes = list(dict.fromkeys([*ROUTES, *dynamic_routes]))
    except (ValueError, KeyError, TypeError, urllib.error.URLError, OSError) as exc:
        print(f"[prerender] Error: {exc}", flush=True)
        return 1

    httpd = SnapshotServer(("127.0.0.1", 0), SPAHandler)
    httpd.api_target = api_target
    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.start()
    print(f"[prerender] Generating static HTML snapshots for {len(all_routes)} routes using {chrome_bin}...", flush=True)
    if not api_target:
        print("[prerender] STATIC-ONLY: no backend requests or dynamic post snapshots; API-dependent pages render their unavailable state (HTTP 503).", flush=True)
    success_count = 0
    try:
        for route in all_routes:
            url = f"http://127.0.0.1:{httpd.server_port}{route}"
            try:
                try:
                    html = render_route(chrome_bin, url)
                finally:
                    httpd.wait_for_requests()
                if httpd.request_errors:
                    raise RuntimeError("; ".join(httpd.request_errors))
                out_dir = DIST_DIR / route.strip("/")
                out_dir.mkdir(parents=True, exist_ok=True)
                out_file = out_dir / "index.html"
                out_file.write_text(html, encoding="utf-8")
                print(f"  OK {route:<30} -> {out_file.relative_to(DIST_DIR)} ({len(html.encode('utf-8')) / 1024:.1f} KB)", flush=True)
                success_count += 1
            except (subprocess.SubprocessError, RuntimeError, OSError, UnicodeError) as exc:
                print(f"  FAIL {route:<30} -> {exc}", flush=True)
            finally:
                with httpd.error_lock:
                    httpd.request_errors.clear()
    finally:
        httpd.shutdown()
        httpd.server_close()
        server_thread.join()
    print(f"[prerender] Successfully generated {success_count}/{len(all_routes)} static route snapshots.", flush=True)
    return 0 if success_count == len(all_routes) else 1


def terminate_prerender(received_signal, _frame):
    # Raising unwinds the active browser/server finally blocks on build cancellation.
    raise SystemExit(128 + received_signal)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, terminate_prerender)
    try:
        sys.exit(prerender())
    except KeyboardInterrupt:
        sys.exit(130)
