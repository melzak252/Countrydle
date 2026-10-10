"""Native Nginx shutdown contract; CI supplies the exact serving image digest."""
import concurrent.futures
import http.client
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from uuid import uuid4


class HeldBackend(http.server.BaseHTTPRequestHandler):
    started = threading.Event()
    released = threading.Event()

    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.path == "/held":
            self.started.set()
            if not self.released.wait(30):
                self.send_error(504)
                return
            payload = b"completed"
        elif self.path == "/status":
            payload = json.dumps({"started": self.started.is_set()}).encode()
        elif self.path == "/release":
            self.released.set()
            payload = b"released"
        elif self.path.startswith("/blog"):
            payload = b'{"posts":[],"total":0}'
        elif self.path == "/explore/modes":
            payload = b'[{"id":"fixture"}]'
        else:
            payload = b"ready"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@unittest.skipUnless(os.environ.get("PUBLISHER_TEST_IMAGE") and shutil.which("docker"),
                     "Set PUBLISHER_TEST_IMAGE to run native serving-image shutdown checks")
class PublisherShutdown(unittest.TestCase):
    def test_default_stop_signal_drains_inflight_response_and_exits_without_sigkill(self):
        image = os.environ["PUBLISHER_TEST_IMAGE"]
        prefix = "countrydle-shutdown-" + uuid4().hex
        network, backend, frontend = prefix + "-net", prefix + "-api", prefix + "-front"

        def docker(*args, timeout=30):
            return subprocess.run(["docker", *args], check=True, capture_output=True,
                                  text=True, timeout=timeout).stdout.strip()

        def address(container, port):
            value = json.loads(docker("inspect", container))[0]
            binding = value["NetworkSettings"]["Ports"][f"{port}/tcp"][0]
            return "http://127.0.0.1:" + binding["HostPort"]

        def get(url):
            with urllib.request.urlopen(url, timeout=10) as response:
                return response.status, response.read()

        def wait_until(condition, message):
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if condition():
                    return
                time.sleep(0.05)
            self.fail(message)

        def available(url):
            try:
                return get(url)[0] == 200
            except (urllib.error.URLError, TimeoutError, http.client.RemoteDisconnected,
                    ConnectionResetError):
                return False

        backend_url = None
        pending = None
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            docker("network", "create", network)
            docker("run", "-d", "--name", backend, "--network", network,
                   "--network-alias", "backend", "-p", "127.0.0.1::8080",
                   "--mount", f"type=bind,src={Path(__file__).resolve()},dst=/shutdown-test.py,readonly",
                   "--entrypoint", "python3", image, "/shutdown-test.py", "--backend")
            backend_url = address(backend, 8080)
            docker("run", "-d", "--name", frontend, "--network", network,
                   "-p", "127.0.0.1::80", "-e", "PUBLISHER_BACKEND_URL=http://backend:8080",
                   "-e", "PUBLISHER_POLL_SECONDS=5", image)
            frontend_url = address(frontend, 80)
            wait_until(lambda: available(frontend_url + "/api/ping"), "Native frontend did not start")
            pending = executor.submit(get, frontend_url + "/api/held")
            wait_until(lambda: json.loads(get(backend_url + "/status")[1])["started"],
                       "The upstream request did not reach the backend")
            configuration = json.loads(docker("image", "inspect", image))[0]["Config"]
            docker("kill", "--signal", configuration.get("StopSignal") or "TERM", frontend)
            wait_until(lambda: not available(frontend_url + "/api/ping"),
                       "The default image stop signal did not stop accepting new requests")
            get(backend_url + "/release")
            self.assertEqual(pending.result(timeout=10), (200, b"completed"))
            self.assertEqual(docker("wait", frontend, timeout=15), "0")
        finally:
            if backend_url:
                try:
                    get(backend_url + "/release")
                except (urllib.error.URLError, TimeoutError):
                    pass
            for container in (frontend, backend):
                subprocess.run(["docker", "rm", "-f", container], capture_output=True, timeout=30)
            subprocess.run(["docker", "network", "rm", network], capture_output=True, timeout=30)
            executor.shutdown(wait=True, cancel_futures=True)
            if pending and pending.done():
                pending.exception()


if __name__ == "__main__":
    if "--backend" in sys.argv:
        http.server.ThreadingHTTPServer(("0.0.0.0", 8080), HeldBackend).serve_forever()
    else:
        unittest.main()
