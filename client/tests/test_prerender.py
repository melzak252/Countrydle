import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("prerender", Path(__file__).parents[1] / "scripts/prerender.py")
prerender = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prerender)


class PrerenderTests(unittest.TestCase):
    def test_slow_api_does_not_block_assets_and_mutations_never_reach_backend(self):
        entered = threading.Event()
        release = threading.Event()
        requests = []

        class Backend(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(self.path)
                entered.set()
                release.wait(2)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"ok":true}')

            def log_message(self, *args):
                pass

        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "index.html").write_text("<html>fixture</html>")
            Path(directory, "asset.js").write_text("asset-content")
            backend = ThreadingHTTPServer(("127.0.0.1", 0), Backend)
            server = prerender.SnapshotServer(("127.0.0.1", 0), prerender.SPAHandler)
            server.api_target = f"http://127.0.0.1:{backend.server_port}"
            threads = [threading.Thread(target=s.serve_forever) for s in (backend, server)]
            for thread in threads:
                thread.start()
            origin = f"http://127.0.0.1:{server.server_port}"
            api_result = []
            try:
                with patch.object(prerender, "DIST_DIR", Path(directory)):
                    api_thread = threading.Thread(target=lambda: api_result.append(urllib.request.urlopen(origin + "/api/slow").read()))
                    api_thread.start()
                    self.assertTrue(entered.wait(2))
                    with urllib.request.urlopen(origin + "/asset.js", timeout=1) as response:
                        self.assertEqual(response.read(), b"asset-content")
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        urllib.request.urlopen(urllib.request.Request(origin + "/api/write", data=b"{}"))
                    self.assertEqual(error.exception.code, 501)
                    release.set()
                    api_thread.join(2)
                    self.assertEqual(api_result, [b'{"ok":true}'])
                    self.assertEqual(requests, ["/slow"])
            finally:
                release.set()
                for running in (server, backend):
                    running.shutdown()
                    running.server_close()
                for thread in threads:
                    thread.join()

    def test_timeout_cleans_up_browser_child_and_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_chrome = Path(directory, "chrome")
            child_pid = Path(directory, "child.pid")
            profile_file = Path(directory, "profile")
            fake_chrome.write_text(
                f"#!{sys.executable}\n"
                "import pathlib, subprocess, sys, time\n"
                "profile = next(arg.split('=', 1)[1] for arg in sys.argv if arg.startswith('--user-data-dir='))\n"
                f"pathlib.Path({str(profile_file)!r}).write_text(profile)\n"
                "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
                "detached = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)', profile], start_new_session=True)\n"
                f"pathlib.Path({str(child_pid)!r}).write_text(str(child.pid) + '\\n' + str(detached.pid))\n"
                "time.sleep(60)\n"
            )
            fake_chrome.chmod(0o755)
            with self.assertRaises(subprocess.TimeoutExpired):
                prerender.render_route(str(fake_chrome), "http://127.0.0.1:1/about", timeout=1)
            self.assertFalse(Path(profile_file.read_text()).exists())
            for pid in child_pid.read_text().splitlines():
                self.assertFalse(Path(f"/proc/{pid}").exists(), f"Owned browser descendant {pid} was not reaped")

    def test_empty_application_is_not_a_successful_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_chrome = Path(directory, "chrome")
            fake_chrome.write_text(
                f"#!{sys.executable}\n"
                "print('<html><body><div id=\"root\"></div></body></html>')\n"
            )
            fake_chrome.chmod(0o755)
            with self.assertRaisesRegex(RuntimeError, "rendered application root"):
                prerender.render_route(str(fake_chrome), "http://127.0.0.1:1/about")

    def test_failed_route_returns_nonzero_and_reports_dynamic_total(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "index.html").write_text("<html>fixture</html>")
            output = io.StringIO()
            with patch.dict(os.environ, {"PRERENDER_API_TARGET": "http://127.0.0.1:8086"}), patch.object(prerender, "DIST_DIR", Path(directory)), patch.object(prerender, "ROUTES", ["/about"]), patch.object(prerender, "find_chrome", return_value="chrome"), patch.object(prerender, "get_dynamic_routes", return_value=["/blog", "/blog/example"]), patch.object(prerender, "render_route", side_effect=["<html>about</html>", subprocess.TimeoutExpired("chrome", 15), "<html>post</html>"]), contextlib.redirect_stdout(output):
                result = prerender.prerender()
            self.assertEqual(result, 1)
            self.assertIn("2/3", output.getvalue())
            self.assertEqual(Path(directory, "blog/example/index.html").read_text(), "<html>post</html>")
            self.assertFalse(Path(directory, "blog/index.html").exists())

    def test_static_only_serves_pages_but_api_reports_real_unavailability(self):
        with patch.dict(os.environ, {"PRERENDER_STATIC_ONLY": "1"}, clear=True):
            self.assertIsNone(prerender.get_api_target())
        with tempfile.TemporaryDirectory() as directory:
            template = b'<html><body><div id="root"></div></body></html>'
            Path(directory, "index.html").write_bytes(template)
            server = prerender.SnapshotServer(("127.0.0.1", 0), prerender.SPAHandler)
            server.api_target = None
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            origin = f"http://127.0.0.1:{server.server_port}"
            try:
                with patch.object(prerender, "DIST_DIR", Path(directory)):
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        urllib.request.urlopen(origin + "/api/blog")
                    self.assertEqual(error.exception.code, 503)
                    self.assertIn(b"explicit static-only", error.exception.read())
                    with urllib.request.urlopen(origin + "/about") as response:
                        self.assertEqual(response.read(), template)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_configured_blog_discovery_failure_never_silently_drops_posts(self):
        with patch.object(prerender.BACKEND_HTTP, "open", side_effect=urllib.error.URLError("configured backend unavailable")):
            with self.assertRaises(urllib.error.URLError):
                prerender.get_dynamic_routes("http://127.0.0.1:8086")

    def test_missing_target_fails_without_contacting_unrelated_api(self):
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), patch.object(prerender, "find_chrome", return_value="chrome"), patch("urllib.request.urlopen") as network, contextlib.redirect_stdout(output):
            self.assertEqual(prerender.prerender(), 1)
        network.assert_not_called()
        self.assertIn("PRERENDER_API_TARGET", output.getvalue())


if __name__ == "__main__":
    unittest.main()
