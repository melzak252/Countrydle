import http.server
import json
import os
import shutil
import socketserver
import subprocess
import threading
import time
import urllib.request
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
]


def get_dynamic_routes() -> list[str]:
    routes = ["/blog"]
    try:
        req = urllib.request.Request("http://127.0.0.1:8080/blog?limit=50", headers={"User-Agent": "Prerender"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for post in data.get("posts", []):
                if "slug" in post:
                    routes.append(f"/blog/{post['slug']}")
    except Exception as exc:
        print(f"[prerender] Notice: Could not fetch dynamic blog routes ({exc}). Using static routes only.")
    return routes


class SPAHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST_DIR), **kwargs)

    def do_GET(self):
        if self.path.startswith("/api/"):
            target_url = f"http://127.0.0.1:8080/{self.path[5:]}"
            try:
                req = urllib.request.Request(target_url, headers={k: v for k, v in self.headers.items() if k.lower() != "host"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    self.send_response(resp.status)
                    for k, v in resp.getheaders():
                        self.send_header(k, v)
                    self.end_headers()
                    self.wfile.write(resp.read())
                    return
            except Exception as e:
                self.send_error(502, f"Bad Gateway: {e}")
                return
        full_path = os.path.join(str(DIST_DIR), self.path.lstrip("/").split("?")[0])
        if not os.path.exists(full_path) or os.path.isdir(full_path):
            self.path = "/index.html"
        return super().do_GET()
def find_chrome() -> str | None:
    if os.environ.get("CHROME_BIN") and shutil.which(os.environ["CHROME_BIN"]):
        return shutil.which(os.environ["CHROME_BIN"])
    for cmd in ["/usr/bin/google-chrome", "google-chrome", "/usr/bin/chromium-browser", "chromium-browser", "chromium"]:
        which = shutil.which(cmd)
        if which:
            return which
    return None


def prerender():
    if not (DIST_DIR / "index.html").exists():
        print(f"[prerender] Error: {DIST_DIR / 'index.html'} does not exist. Run 'vite build' first.")
        return

    chrome_bin = find_chrome()
    if not chrome_bin:
        print("[prerender] Warning: Chrome/Chromium not found. Skipping static HTML snapshot generation.")
        return

    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", 0), SPAHandler)
    port = httpd.server_address[1]
    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    time.sleep(0.5)

    all_routes = list(ROUTES) + get_dynamic_routes()
    print(f"[prerender] Generating static HTML snapshots for {len(all_routes)} routes using {chrome_bin}...")

    success_count = 0
    try:
        for route in all_routes:
            url = f"http://127.0.0.1:{port}{route}"
            try:
                html = subprocess.check_output(
                    [
                        chrome_bin,
                        "--headless=new",
                        "--no-sandbox",
                        "--disable-gpu",
                        "--virtual-time-budget=2000",
                        "--dump-dom",
                        url,
                    ],
                    timeout=15,
                ).decode("utf-8")

                # Determine target output directory
                clean_route = route.strip("/")
                out_dir = DIST_DIR / clean_route
                out_dir.mkdir(parents=True, exist_ok=True)
                out_file = out_dir / "index.html"

                out_file.write_text(html, encoding="utf-8")
                size_kb = len(html.encode("utf-8")) / 1024
                print(f"  ✓ {route:<30} -> {out_file.relative_to(DIST_DIR)} ({size_kb:.1f} KB)")
                success_count += 1
            except Exception as e:
                print(f"  ✗ {route:<30} -> Error: {e}")
    finally:
        httpd.shutdown()
        httpd.server_close()

    print(f"[prerender] Successfully generated {success_count}/{len(ROUTES)} static route snapshots.")


if __name__ == "__main__":
    prerender()
