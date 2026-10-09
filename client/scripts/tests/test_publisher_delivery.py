"""Disposable artifact/API fixtures; production Chromium/HTTP smoke is separate."""
import contextlib
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runtime = load("publisher-runtime", "publisher-runtime.py")
sys.modules["publisher-runtime"] = runtime
capture = load("publisher_capture_test", "publisher-capture.py")
HTML = '<!doctype html><html><head><title>Fixture factual page</title></head><body><main><h1>Fixture factual page</h1><p>' + ('Recorded geographical fixture facts. ' * 12) + '</p></main></body></html>'


def post(slug, identifier=1, reviewed=True):
    return {"id": identifier, "slug": slug, "date": "2020-01-02" if identifier == 1 else "2020-01-01", "title": slug, "summary": "Fixture facts", "created_at": None, "updated_at": "2026-01-01T00:00:00.000001Z", "editorial_status": "reviewed" if reviewed else "unreviewed", "reviewed_at": "2026-01-01T00:00:00Z" if reviewed else None}


class ArtifactSetup:
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.assets = self.root / "assets"
        self.assets.mkdir()
        (self.assets / "spa-shell.html").write_text('<!doctype html><div id="root"></div><script src="/assets/app.js"></script>')
        (self.assets / "assets").mkdir()
        (self.assets / "assets" / "app.js").write_text("fixture bundle")
        self.output = self.root / "snapshots"
        self.output.mkdir()
        self.posts = {"one": post("one"), "two": post("two", 2)}
        self.modes = [{"id": "countrydle", "name": "Countrydle"}]
        self.state = runtime.PublisherState(self.assets, self.output, 60)

    def tearDown(self):
        self.state.close()
        self.temporary.cleanup()

    def release(self, name="release-fixture", posts=None, statuses=None, build=None):
        posts = self.posts if posts is None else posts
        statuses = statuses or {}
        release = self.output / name
        release.mkdir()
        build = build or runtime.asset_fingerprint(self.assets)
        routes = {}
        for route in (*runtime.ROUTES, "/blog", *("/blog/" + slug for slug in posts)):
            status = statuses.get(route, 200)
            item = {"status": status, "version": runtime.route_version(route, posts, self.modes, build)}
            if status == 200:
                target = runtime.output_file(release, route)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(HTML)
                item["sha256"] = hashlib.sha256(HTML.encode()).hexdigest()
            routes[route] = item
        manifest = {"schema": 1, "build_fingerprint": build, "captured_at": "2026-01-01T00:00:00Z", "posts": {"status": 200, "metadata": posts}, "modes": {"status": 200, "metadata": self.modes}, "routes": routes}
        (release / ".publisher-manifest.json").write_text(json.dumps(manifest))
        (release / ".publisher-posts.json").write_text(json.dumps(posts))
        self.promote(release)
        return release

    def promote(self, release):
        temporary = self.output / ".next-current"
        temporary.symlink_to(release.name, target_is_directory=True)
        temporary.replace(self.output / "current")

    def refresh(self, posts=None, blog_error=None, modes_error=None):
        with patch.object(runtime, "published_posts", side_effect=blog_error, return_value=self.posts if posts is None else posts), patch.object(runtime, "exploration_modes", side_effect=modes_error, return_value=self.modes):
            runtime.refresh(self.state, "http://fixture-api")

    @contextlib.contextmanager
    def http(self):
        server = runtime.PublisherServer(("127.0.0.1", 0), self.state)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            def request(path):
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
                connection.request("GET", path)
                response = connection.getresponse()
                result = response.status, dict(response.getheaders()), response.read()
                connection.close()
                return result
            yield request
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


class ArtifactFixture(ArtifactSetup, unittest.TestCase):
    def test_article_failure_isolated_from_home_other_article_and_health(self):
        self.release(statuses={"/blog/one": 503})
        self.refresh()
        with self.http() as request:
            for route in ("/", "/faq", "/blog/two", "/healthz"):
                self.assertEqual(request(route)[0], 200, route)
            self.assertEqual(request("/blog/one")[0], 503)

    def test_blog_outage_is_not_fake_empty_and_explore_remains_available(self):
        self.release()
        self.refresh(blog_error=runtime.PublisherError("list unavailable"))
        with self.http() as request:
            for route in ("/", "/about", "/explore", "/healthz"):
                self.assertEqual(request(route)[0], 200, route)
            self.assertEqual(request("/blog")[0], 503)
            self.assertEqual(request("/blog/one")[0], 503)

    def test_explore_outage_affects_no_blog_or_static_route(self):
        self.release()
        self.refresh(modes_error=runtime.PublisherError("modes unavailable"))
        with self.http() as request:
            self.assertEqual(request("/explore")[0], 503)
            for route in ("/", "/blog/one", "/explore/modes/countrydle", "/healthz"):
                self.assertEqual(request(route)[0], 200, route)

    def test_revoke_review_and_version_changes_never_serve_stale_article(self):
        self.release()
        changed = {**self.posts, "one": {**self.posts["one"], "editorial_status": "unreviewed", "reviewed_at": None, "updated_at": "2026-01-02T00:00:00.000002Z"}}
        self.refresh(posts=changed)
        with self.http() as request:
            self.assertEqual(request("/blog/one")[0], 503)
            self.assertEqual(request("/blog")[0], 503)
            self.assertEqual(request("/")[0], 200)
            self.assertEqual(request("/healthz")[0], 200)

    def test_all_metadata_changes_invalidate_not_only_update_timestamp(self):
        self.release()
        changed = {**self.posts, "one": {**self.posts["one"], "summary": "Corrected public facts"}}
        self.refresh(posts=changed)
        with self.http() as request:
            self.assertEqual(request("/blog/one")[0], 503)

    def test_deleted_unknown_future_and_date_alias(self):
        self.release()
        self.refresh()
        with self.http() as request:
            status, headers, _body = request("/blog/2020-01-02")
            self.assertEqual(status, 308)
            self.assertEqual(headers["Location"], "/blog/one")
            self.assertEqual(request("/blog/missing")[0], 404)
            self.assertEqual(request("/blog/2999-01-01")[0], 404)
            self.assertEqual(request("/blog/%2e%2e/private")[0], 404)
            self.assertEqual(request("/blog%2Fone")[0], 404)
            self.assertEqual(request("/%62log/one")[0], 404)
        self.refresh(posts={"two": self.posts["two"]})
        with self.http() as request:
            self.assertEqual(request("/blog/one")[0], 404)
            self.assertEqual(request("/blog/2020-01-02")[0], 404)

    def test_wrong_bundle_current_retains_previously_validated_release(self):
        first = self.release()
        self.refresh()
        self.release("release-wrong", build="0" * 64)
        self.refresh()
        self.assertEqual(self.state.current, first)
        with self.http() as request:
            self.assertEqual(request("/")[0], 200)
            self.assertEqual(request("/healthz")[0], 200)

    def test_missing_initial_static_is_503_never_spa_success(self):
        self.release(statuses={"/faq": 503})
        self.refresh()
        with self.http() as request:
            self.assertEqual(request("/faq")[0], 503)
            self.assertEqual(request("/")[0], 503)
            self.assertEqual(request("/healthz")[0], 503)

    def test_missing_initial_artifact_even_with_spa_shell_is_503(self):
        self.refresh()
        with self.http() as request:
            self.assertEqual(request("/")[0], 503)
            self.assertEqual(request("/healthz")[0], 503)

    def test_tampered_file_fails_validator(self):
        release = self.release()
        runtime.output_file(release, "/faq").write_text("truncated")
        with self.assertRaises(runtime.PublisherError):
            runtime.validate_release(release, self.assets)

    def test_matching_new_release_restores_changed_route_atomically(self):
        self.release()
        self.refresh()
        changed = {**self.posts, "one": {**self.posts["one"], "updated_at": "2026-01-03T00:00:00Z"}}
        self.refresh(posts=changed)
        release = self.release("release-correction", posts=changed)
        self.refresh(posts=changed)
        self.assertEqual(self.state.current, release)
        with self.http() as request:
            self.assertEqual(request("/blog/one")[0], 200)

    def test_polling_only_fetches_public_metadata_and_never_mutates_volume(self):
        release = self.release()
        before = {str(path.relative_to(self.output)): path.read_bytes() for path in release.rglob("*") if path.is_file()}
        self.refresh()
        after = {str(path.relative_to(self.output)): path.read_bytes() for path in release.rglob("*") if path.is_file()}
        self.assertEqual(before, after)
        self.assertEqual((self.output / "current").readlink(), Path(release.name))

    def test_spa_shell_disguised_as_snapshot_is_rejected(self):
        release = self.release()
        shell = (self.assets / "spa-shell.html").read_bytes()
        runtime.output_file(release, "/").write_bytes(shell)
        manifest = json.loads((release / runtime.MANIFEST).read_text())
        manifest["routes"]["/"]["sha256"] = hashlib.sha256(shell).hexdigest()
        (release / runtime.MANIFEST).write_text(json.dumps(manifest))
        with self.assertRaises(runtime.PublisherError):
            runtime.validate_release(release, self.assets)

    def test_list_order_is_part_of_index_version(self):
        self.release()
        self.refresh(posts=dict(reversed(list(self.posts.items()))))
        with self.http() as request:
            self.assertEqual(request("/blog")[0], 503)

    def test_metadata_freshness_expires_blog_not_static_health(self):
        self.release()
        self.refresh()
        self.state.blog_success -= self.state.freshness + 1
        with self.http() as request:
            self.assertEqual(request("/blog/one")[0], 503)
            self.assertEqual(request("/")[0], 200)
            self.assertEqual(request("/healthz")[0], 200)

    def test_malformed_known_summary_has_503_canonical_and_308_date_alias(self):
        self.posts["one"] = {**self.posts["one"], "summary": ""}
        self.release(statuses={"/blog/one": 503, "/blog": 503})
        self.refresh()
        with self.http() as request:
            self.assertEqual(request("/blog/one")[0], 503)
            status, headers, _body = request("/blog/2020-01-02")
            self.assertEqual(status, 308)
            self.assertEqual(headers["Location"], "/blog/one")
            self.assertEqual(request("/")[0], 200)
            self.assertEqual(request("/healthz")[0], 200)


class CaptureFixture(ArtifactSetup, unittest.TestCase):
    @contextlib.contextmanager
    def renderer(self, _assets, _backend, posts, _timeout, **_kwargs):
        class Server:
            failures = []
        class Browser:
            def capture(_self, _server, route, _origin):
                if route == "/blog/one":
                    raise runtime.PublisherError("Malformed mandatory article data")
                return HTML
        yield Server(), Browser()

    def run_capture(self, blog_error=None, modes_error=None):
        with patch.object(capture.runtime, "published_posts", side_effect=blog_error, return_value=self.posts), patch.object(capture.runtime, "exploration_modes", side_effect=modes_error, return_value=self.modes), patch.object(capture, "capture_session", self.renderer):
            return capture.publish(self.assets, self.output, "http://fixture-api", "https://fixture.example", 5)

    def test_one_shot_publishes_readable_unaffected_routes_and_failure_manifest(self):
        release = self.run_capture()
        manifest = runtime.validate_release(release, self.assets)
        self.assertEqual(manifest["routes"]["/blog/one"]["status"], 503)
        self.assertFalse(runtime.output_file(release, "/blog/one").exists())
        self.assertIn("Fixture factual page", runtime.output_file(release, "/blog/two").read_text())
        self.assertEqual((self.output / "current").resolve(), release)
        self.refresh()
        with self.http() as request:
            self.assertEqual(request("/blog/one")[0], 503)
            self.assertEqual(request("/blog/two")[0], 200)
            self.assertEqual(request("/healthz")[0], 200)

    def test_backend_blog_failure_publishes_static_but_not_fake_empty_blog(self):
        release = self.run_capture(blog_error=runtime.PublisherError("backend unavailable"))
        manifest = runtime.validate_release(release, self.assets)
        self.assertEqual(manifest["posts"]["status"], 503)
        self.assertEqual(manifest["routes"]["/blog"]["status"], 503)
        self.assertEqual(manifest["routes"]["/"]["status"], 200)
        self.assertEqual(manifest["routes"]["/explore"]["status"], 200)

    def test_modes_failure_does_not_abort_capture_of_static_or_articles(self):
        release = self.run_capture(modes_error=runtime.PublisherError("modes unavailable"))
        manifest = runtime.validate_release(release, self.assets)
        self.assertEqual(manifest["routes"]["/explore"]["status"], 503)
        self.assertEqual(manifest["routes"]["/blog/two"]["status"], 200)
        self.assertEqual(manifest["routes"]["/"]["status"], 200)

    def test_unchanged_release_reuses_uuid_without_launching_renderer(self):
        original = self.release()
        with patch.object(capture.runtime, "published_posts", return_value=self.posts), patch.object(capture.runtime, "exploration_modes", return_value=self.modes), patch.object(capture, "capture_session") as renderer:
            release = capture.publish(self.assets, self.output, "http://fixture-api", "https://fixture.example", 5)
        self.assertEqual(release, original)
        renderer.assert_not_called()

    def test_changed_failed_article_drops_previous_reviewed_html(self):
        previous = self.release()
        self.posts["one"] = {**self.posts["one"], "editorial_status": "unreviewed", "reviewed_at": None, "updated_at": "2026-01-04T00:00:00Z"}
        release = self.run_capture()
        self.assertNotEqual(previous, release)
        self.assertIn("Fixture factual page", runtime.output_file(previous, "/blog/one").read_text())
        self.assertFalse(runtime.output_file(release, "/blog/one").exists())
        self.assertEqual(runtime.validate_release(release, self.assets)["routes"]["/blog/one"]["status"], 503)

    def test_deleted_article_absent_from_new_release(self):
        self.release()
        self.posts = {"two": self.posts["two"]}
        release = self.run_capture()
        manifest = runtime.validate_release(release, self.assets)
        self.assertNotIn("/blog/one", manifest["routes"])
        self.assertFalse(runtime.output_file(release, "/blog/one").exists())

    def test_browser_launch_failure_keeps_unchanged_static_snapshots(self):
        self.release()
        self.posts["one"] = {**self.posts["one"], "updated_at": "2026-01-05T00:00:00Z"}
        with patch.object(capture.runtime, "published_posts", return_value=self.posts), patch.object(capture.runtime, "exploration_modes", return_value=self.modes), patch.object(capture, "capture_session", side_effect=runtime.PublisherError("Renderer failed")):
            release = capture.publish(self.assets, self.output, "http://fixture-api", "https://fixture.example", 5)
        manifest = runtime.validate_release(release, self.assets)
        self.assertEqual(manifest["routes"]["/"]["status"], 200)
        self.assertEqual(manifest["routes"]["/blog/one"]["status"], 503)
        self.refresh()
        with self.http() as request:
            self.assertEqual(request("/healthz")[0], 200)
            self.assertEqual(request("/blog/one")[0], 503)

    def test_modes_change_during_capture_invalidates_only_explore(self):
        changed_modes = [*self.modes, {"id": "fixture-new-mode", "name": "Fixture mode"}]
        with patch.object(capture.runtime, "published_posts", return_value=self.posts), patch.object(capture.runtime, "exploration_modes", side_effect=[self.modes, changed_modes]), patch.object(capture, "capture_session", self.renderer):
            release = capture.publish(self.assets, self.output, "http://fixture-api", "https://fixture.example", 5)
        manifest = runtime.validate_release(release, self.assets)
        self.assertEqual(manifest["routes"]["/explore"]["status"], 503)
        self.assertEqual(manifest["routes"]["/blog/two"]["status"], 200)
        self.assertEqual(manifest["routes"]["/"]["status"], 200)

    def test_backend_list_failure_after_capture_invalidates_blog_not_static(self):
        with patch.object(capture.runtime, "published_posts", side_effect=[self.posts, runtime.PublisherError("List unavailable after rendering")]), patch.object(capture.runtime, "exploration_modes", return_value=self.modes), patch.object(capture, "capture_session", self.renderer):
            release = capture.publish(self.assets, self.output, "http://fixture-api", "https://fixture.example", 5)
        manifest = runtime.validate_release(release, self.assets)
        self.assertEqual(manifest["posts"]["status"], 503)
        self.assertEqual(manifest["routes"]["/blog/two"]["status"], 503)
        self.assertFalse(runtime.output_file(release, "/blog/two").exists())
        self.assertEqual(manifest["routes"]["/"]["status"], 200)
        self.assertEqual(manifest["routes"]["/explore"]["status"], 200)

    def test_deletion_during_capture_removes_old_html_and_metadata(self):
        remaining = {"two": self.posts["two"]}
        with patch.object(capture.runtime, "published_posts", side_effect=[self.posts, remaining]), patch.object(capture.runtime, "exploration_modes", return_value=self.modes), patch.object(capture, "capture_session", self.renderer):
            release = capture.publish(self.assets, self.output, "http://fixture-api", "https://fixture.example", 5)
        manifest = runtime.validate_release(release, self.assets)
        self.assertNotIn("one", manifest["posts"]["metadata"])
        self.assertNotIn("/blog/one", manifest["routes"])
        self.assertFalse(runtime.output_file(release, "/blog/one").exists())
        self.assertEqual(manifest["routes"]["/"]["status"], 200)


class MetadataFixtures(unittest.TestCase):
    def test_known_invalid_row_does_not_erase_other_published_metadata(self):
        rows = [post("one"), {**post("two", 2), "summary": ""}]
        with patch.object(runtime, "fetch_bytes", return_value=json.dumps({"posts": rows, "total": 2}).encode()):
            actual = runtime.published_posts("http://fixture-api")
        self.assertEqual(set(actual), {"one", "two"})
        self.assertIsNone(runtime.post_error(actual["one"]))
        self.assertIsNotNone(runtime.post_error(actual["two"]))

    def test_today_future_metadata_never_becomes_known_public_article(self):
        rows = [post("one"), {**post("future", 2), "date": "2999-01-01"}]
        with patch.object(runtime, "fetch_bytes", return_value=json.dumps({"posts": rows, "total": 2}).encode()):
            actual = runtime.published_posts("http://fixture-api")
        self.assertEqual(set(actual), {"one"})

    def test_failed_mandatory_index_does_not_become_empty_success(self):
        with patch.object(runtime, "fetch_bytes", return_value=b'{"posts": [], "total": 4}'):
            with self.assertRaises(runtime.PublisherError):
                runtime.published_posts("http://fixture-api")


class TransportRejections(ArtifactSetup, unittest.TestCase):
    def promote_command(self, missing_environment=False):
        shims = self.root / "bin"
        shims.mkdir()
        marker = self.root / "network-called"
        for name in ("ssh", "ssh-keygen", "rsync"):
            executable = shims / name
            executable.write_text(f"#!/bin/sh\nprintf called >> '{marker}'\nexit 99\n")
            executable.chmod(0o755)
        environment = {key: value for key, value in os.environ.items() if not key.startswith("PUBLISHER_")}
        environment["PATH"] = str(shims) + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin")
        if not missing_environment:
            environment.update({"PUBLISHER_SSH_HOST": "fixture.invalid", "PUBLISHER_SSH_USER": "publisher", "PUBLISHER_SSH_KEY": "disposable invalid fixture key", "PUBLISHER_SSH_KNOWN_HOSTS": "disposable invalid fixture host key", "PUBLISHER_REMOTE_DIR": "/srv/publisher", "PUBLISHER_CONTAINER_ENGINE": "docker", "PUBLISHER_FRONTEND_CONTAINER": "fixture-serving"})
        result = subprocess.run(["bash", str(SCRIPTS / "publish-snapshots.sh"), str(self.output)], env=environment, text=True, capture_output=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(marker.exists(), result.stderr)
        return result

    def test_missing_deployment_environment_fails_before_network(self):
        result = self.promote_command(missing_environment=True)
        self.assertIn("PUBLISHER_SSH_HOST", result.stderr)

    def test_missing_current_pointer_fails_before_network(self):
        result = self.promote_command()
        self.assertIn("current symlink", result.stderr)

    def test_corrupt_snapshot_fails_local_validation_before_network(self):
        release = self.release("release-" + "a" * 32)
        runtime.output_file(release, "/faq").write_text("corrupt fixture")
        result = self.promote_command()
        self.assertIn("local snapshot manifest/content validation failed", result.stderr)


class TransportPromotionFixtures(ArtifactSetup, unittest.TestCase):
    """Run the real transport; only SSH/rsync/engine boundaries are disposable."""

    def setUp(self):
        super().setUp()
        self.remote = self.root / "mounted-snapshots"
        self.remote.mkdir()
        self.bin = self.root / "transport-bin"
        self.bin.mkdir()
        self.calls = self.root / "engine-calls.jsonl"
        self.ssh_calls = self.root / "ssh-calls.jsonl"
        self.environment = {key: value for key, value in os.environ.items() if not key.startswith("PUBLISHER_")}
        self.environment.update({
            "PATH": str(self.bin) + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"),
            "PUBLISHER_SSH_HOST": "fixture.invalid",
            "PUBLISHER_SSH_USER": "publisher",
            "PUBLISHER_SSH_KEY": "disposable fixture key",
            "PUBLISHER_SSH_KNOWN_HOSTS": "disposable fixture host key",
            "PUBLISHER_REMOTE_DIR": str(self.remote),
            "PUBLISHER_CONTAINER_ENGINE": "docker",
            "PUBLISHER_FRONTEND_CONTAINER": "fixture-serving",
            "FIXTURE_ASSETS": str(self.assets),
            "FIXTURE_RUNTIME": str(SCRIPTS / "publisher-runtime.py"),
            "FIXTURE_REMOTE": str(self.remote),
            "FIXTURE_ENGINE_CALLS": str(self.calls),
            "FIXTURE_SSH_CALLS": str(self.ssh_calls),
        })
        self.shim("ssh-keygen", "raise SystemExit(0)\n")
        self.shim("ssh", """
import json
import os
import sys
with open(os.environ["FIXTURE_SSH_CALLS"], "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
position = sys.argv.index("publisher@fixture.invalid")
command = sys.argv[position + 1:]
os.execvp(command[0], command)
""")
        self.shim("rsync", """
import os
from pathlib import Path
import shutil
import sys
source = sys.argv[-2]
target = Path(sys.argv[-1].split(":", 1)[1])
if os.environ.get("FIXTURE_INTERRUPTED_UPLOAD"):
    (target / "partial").write_text("Interrupted disposable transfer")
    raise SystemExit(78)
if source.endswith("/"):
    shutil.copytree(source, target, dirs_exist_ok=True)
else:
    shutil.copyfile(source, target)
""")
        engine = """
import json
import os
from pathlib import Path
import subprocess
import sys
with open(os.environ["FIXTURE_ENGINE_CALLS"], "a") as log:
    log.write(json.dumps([Path(sys.argv[0]).name, *sys.argv[1:]]) + "\\n")
if os.environ.get("FIXTURE_CONTAINER_UNAVAILABLE"):
    raise SystemExit("Disposable serving container is unavailable")
if sys.argv[1] == "inspect":
    print(json.dumps([{"Id": "d" * 64, "State": {"Running": True}}]))
elif sys.argv[1] == "exec":
    assert sys.argv[2:5] == ["--", "d" * 64, "python3"]
    assert sys.argv[5] == "/usr/local/lib/countrydle/publisher-runtime.py"
    arguments = [argument.replace("/var/run/countrydle-publisher", os.environ["FIXTURE_REMOTE"]).replace("/usr/share/nginx/html", os.environ["FIXTURE_ASSETS"]) for argument in sys.argv[6:]]
    raise SystemExit(subprocess.run([sys.executable, os.environ["FIXTURE_RUNTIME"], *arguments]).returncode)
else:
    raise SystemExit("Unexpected disposable engine command")
"""
        self.shim("docker", engine)
        self.shim("podman", engine)

    def shim(self, name, body):
        path = self.bin / name
        path.write_text("#!" + sys.executable + "\n" + body)
        path.chmod(0o755)

    def transfer(self, **settings):
        return subprocess.run(
            ["bash", str(SCRIPTS / "publish-snapshots.sh"), str(self.output)],
            env={**self.environment, **settings}, text=True, capture_output=True, timeout=30,
        )

    def assert_promoted(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def use_remote_reader(self):
        self.state.close()
        self.state = runtime.PublisherState(self.assets, self.remote, 60)
        self.refresh()

    def test_wrong_bundle_promotion_preserves_working_current_after_reader_restart(self):
        first = self.release("release-" + "1" * 32)
        self.assert_promoted(self.transfer())
        self.use_remote_reader()
        self.release("release-" + "2" * 32, build="0" * 64)
        result = self.transfer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not match deployed shell/assets", result.stderr)
        self.assertEqual((self.remote / "current").readlink(), Path(first.name))
        self.assertFalse((self.remote / ("release-" + "2" * 32)).exists())
        self.use_remote_reader()
        with self.http() as request:
            self.assertEqual(request("/")[0], 200)
            self.assertEqual(request("/healthz")[0], 200)

    def test_good_and_repeated_promotion_validate_deployed_assets_with_explicit_podman(self):
        release = self.release("release-" + "3" * 32)
        self.assert_promoted(self.transfer(PUBLISHER_CONTAINER_ENGINE="podman"))
        self.assert_promoted(self.transfer(PUBLISHER_CONTAINER_ENGINE="podman"))
        self.assertEqual((self.remote / "current").readlink(), Path(release.name))
        executions = [json.loads(line) for line in self.calls.read_text().splitlines() if json.loads(line)[1] == "exec"]
        self.assertGreaterEqual(len(executions), 2)
        for command in executions:
            self.assertEqual(command[0], "podman")
            self.assertIn("--assets-dir", command)
            self.assertIn("/usr/share/nginx/html", command)
        for arguments in map(json.loads, self.ssh_calls.read_text().splitlines()):
            self.assertIn("StrictHostKeyChecking=yes", arguments)
            self.assertIn("GlobalKnownHostsFile=/dev/null", arguments)

    def test_already_current_is_not_success_when_deployed_bundle_changed(self):
        release = self.release("release-" + "4" * 32)
        self.assert_promoted(self.transfer())
        (self.assets / "assets" / "app.js").write_text("Different deployed fixture bundle")
        result = self.transfer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not match deployed shell/assets", result.stderr)
        self.assertEqual((self.remote / "current").readlink(), Path(release.name))

    def test_unavailable_container_and_interrupted_upload_preserve_current(self):
        first = self.release("release-" + "5" * 32)
        self.assert_promoted(self.transfer())
        second = self.release("release-" + "6" * 32)
        for settings in ({"FIXTURE_CONTAINER_UNAVAILABLE": "1"}, {"FIXTURE_INTERRUPTED_UPLOAD": "1"}):
            with self.subTest(settings=settings):
                result = self.transfer(**settings)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual((self.remote / "current").readlink(), Path(first.name))
                self.assertFalse((self.remote / second.name).exists())
                self.assertFalse(list(self.remote.glob(".incoming-*")))
        self.use_remote_reader()
        with self.http() as request:
            self.assertEqual(request("/")[0], 200)

    def test_retirement_bounds_archives_without_deleting_a_live_reader_release(self):
        first = self.release("release-" + "7" * 32)
        self.assert_promoted(self.transfer())
        self.use_remote_reader()
        for value in range(8, 13):
            newest = self.release("release-" + format(value, "032x"))
            self.assert_promoted(self.transfer())
        incompatible = self.release("release-" + "e" * 32, build="0" * 64)
        shutil.copytree(incompatible, self.remote / incompatible.name)
        self.promote(newest)
        self.assert_promoted(self.transfer())
        archives = list(self.remote.glob("release-*"))
        self.assertEqual(len(archives), 4)
        self.assertTrue((self.remote / first.name).is_dir())
        self.assertFalse((self.remote / incompatible.name).exists())
        with self.http() as request:
            self.assertEqual(request("/")[0], 200)
        self.state.load_current()
        self.assertEqual(self.state.current, self.remote / newest.name)
        self.assert_promoted(self.transfer())
        self.assertEqual(len(list(self.remote.glob("release-*"))), 3)
        self.assertFalse((self.remote / first.name).exists())
        self.assertTrue(runtime.output_file(self.state.current, "/").is_file())

    def test_inflight_http_payload_keeps_lease_until_reader_switch_finishes(self):
        first = self.release("release-" + "a" * 32)
        self.assert_promoted(self.transfer())
        self.use_remote_reader()
        for value in range(20, 23):
            self.release("release-" + format(value, "032x"))
            self.assert_promoted(self.transfer())
        reading = threading.Event()
        resume = threading.Event()
        switching = threading.Event()
        switched = threading.Event()
        responses = []
        original_read = Path.read_bytes
        target = runtime.output_file(self.remote / first.name, "/")

        def paused_read(path):
            if path == target:
                reading.set()
                if not resume.wait(10):
                    raise TimeoutError("Disposable HTTP fixture was not released")
            return original_read(path)

        def switch():
            switching.set()
            self.state.load_current()
            switched.set()

        with self.http() as request, patch.object(Path, "read_bytes", paused_read):
            requester = threading.Thread(target=lambda: responses.append(request("/")))
            loader = threading.Thread(target=switch)
            requester.start()
            try:
                self.assertTrue(reading.wait(5))
                self.assert_promoted(self.transfer())
                loader.start()
                self.assertTrue(switching.wait(5))
                self.assertFalse(switched.wait(0.1))
                self.assertTrue((self.remote / first.name).is_dir())
            finally:
                resume.set()
                requester.join(10)
                if loader.ident is not None:
                    loader.join(10)
            self.assertFalse(requester.is_alive())
            self.assertFalse(loader.is_alive())
            self.assertEqual(responses[0][0], 200)
        self.assert_promoted(self.transfer())
        self.assertFalse((self.remote / first.name).exists())

    def test_explicit_engine_and_frontend_settings_fail_before_network(self):
        self.release("release-" + "f" * 32)
        for setting, value in (("PUBLISHER_CONTAINER_ENGINE", ""), ("PUBLISHER_CONTAINER_ENGINE", "docker;false"), ("PUBLISHER_FRONTEND_CONTAINER", ""), ("PUBLISHER_FRONTEND_CONTAINER", "--privileged")):
            with self.subTest(setting=setting, value=value):
                result = self.transfer(**{setting: value})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(setting, result.stderr)
                self.assertFalse(self.ssh_calls.exists())


class BrowserLaunchFixtures(unittest.TestCase):
    def test_arbitrary_uid_inherited_root_home_gets_private_writable_directories(self):
        renderer = sys.modules["prerender"]
        observed = {}

        def launch(arguments, **options):
            environment = options["env"]
            for variable in ("HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_RUNTIME_DIR"):
                directory = Path(environment[variable])
                self.assertNotEqual(environment[variable], "/root")
                self.assertTrue(directory.is_dir())
                self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
                (directory / "writable-fixture").write_text("disposable")
            user_data = Path(next(argument.split("=", 1)[1] for argument in arguments if argument.startswith("--user-data-dir=")))
            self.assertTrue(user_data.is_dir())
            self.assertEqual(user_data.parent, Path(environment["HOME"]).parent)
            observed["root"] = user_data.parent
            observed["stderr"] = options["stderr"]
            options["stderr"].write(b"disposable launch fixture diagnostic")
            from types import SimpleNamespace
            return SimpleNamespace(poll=lambda: 133)

        with patch.dict(os.environ, {"HOME": "/root", "XDG_CONFIG_HOME": "/root", "XDG_CACHE_HOME": "/root", "XDG_DATA_HOME": "/root", "XDG_RUNTIME_DIR": "/root"}), patch.object(renderer.shutil, "which", return_value="/fixture/chromium"), patch.object(renderer.subprocess, "Popen", side_effect=launch):
            with self.assertRaisesRegex(runtime.PublisherError, "exit 133.*disposable launch fixture diagnostic"):
                with renderer.Browser(5):
                    self.fail("A failed renderer must never become ready")
        self.assertFalse(observed["root"].exists())
        self.assertTrue(observed["stderr"].closed)

    def test_launch_diagnostic_is_bounded_and_retains_real_error_tail(self):
        renderer = sys.modules["prerender"]

        def launch(_arguments, **options):
            options["stderr"].write(b"discardable log prefix " * 1000 + b"fixture crashpad database error")
            from types import SimpleNamespace
            return SimpleNamespace(poll=lambda: 133)

        with patch.object(renderer.shutil, "which", return_value="/fixture/chromium"), patch.object(renderer.subprocess, "Popen", side_effect=launch):
            with self.assertRaises(runtime.PublisherError) as error:
                with renderer.Browser(5):
                    self.fail("A failed renderer must never become ready")
        self.assertIn("fixture crashpad database error", str(error.exception))
        self.assertLess(len(str(error.exception)), 4200)

    def test_spawn_os_failure_cleans_private_profile_and_stderr(self):
        renderer = sys.modules["prerender"]
        with patch.object(renderer.shutil, "which", return_value="/fixture/chromium"), patch.object(renderer.subprocess, "Popen", side_effect=OSError("disposable spawn fixture")):
            browser = renderer.Browser(5)
            profile = Path(browser.profile.name)
            with self.assertRaisesRegex(OSError, "disposable spawn fixture"):
                browser.__enter__()
        self.assertFalse(profile.exists())
        self.assertTrue(browser.stderr.closed)


if __name__ == "__main__":
    unittest.main()
