"""Publish immutable real-browser snapshots, then exit (watch is explicit dev only).

python3 publisher-capture.py --assets-dir PATH --output-dir PATH
The serving container never runs or imports this worker. Route failures are explicit
503 manifest entries without HTML; verified static pages survive API/job failures.
"""

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import uuid

runtime = importlib.import_module("publisher-runtime")
from prerender import atomic_write, capture_session, configuration, shell_path


def previous_release(output, build):
    try:
        link = output / "current"
        if not link.is_symlink():
            return None, None
        release = link.resolve(strict=True)
        if release.parent != output or not release.name.startswith("release-"):
            return None, None
        return release, runtime.validate_release(release, expected_build=build)
    except (OSError, runtime.PublisherError) as error:
        print(f"[publisher-capture] Previous artifact cannot be reused: {error}", flush=True)
        return None, None


def metadata(backend, previous):
    try:
        posts = runtime.published_posts(backend)
        blog_ok = True
    except Exception as error:
        print(f"[publisher-capture] Blog metadata unavailable: {error}", flush=True)
        posts = previous["posts"]["metadata"] if previous else {}
        blog_ok = False
    try:
        modes = runtime.exploration_modes(backend)
        modes_ok = True
    except Exception as error:
        print(f"[publisher-capture] Explore metadata unavailable: {error}", flush=True)
        modes = previous["modes"]["metadata"] if previous else []
        modes_ok = False
    return posts, blog_ok, modes, modes_ok


def remove_html(staging, route):
    target = runtime.output_file(staging, route)
    if target.exists():
        target.unlink()


def failed_route(staging, routes, route, posts, modes, build):
    remove_html(staging, route)
    routes[route] = {"status": 503, "version": runtime.route_version(route, posts, modes, build)}


def route_allowed(route, posts, blog_ok, modes_ok):
    if route == "/explore":
        return modes_ok
    if route.startswith("/blog"):
        if not blog_ok:
            return False
        if route.startswith("/blog/"):
            return runtime.post_error(posts[route.removeprefix("/blog/")]) is None
    return True


def publish(assets, output, backend, public_origin, timeout):
    """Produce a complete release; only its current pointer is ever mutable."""
    assets, output = Path(assets).resolve(), Path(output).resolve()
    shell_path(assets)
    build = runtime.asset_fingerprint(assets)
    output.mkdir(parents=True, exist_ok=True)
    with (output / ".publisher.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        previous, previous_manifest = previous_release(output, build)
        posts, blog_ok, modes, modes_ok = metadata(backend, previous_manifest)
        required = {*runtime.ROUTES, "/blog", *("/blog/" + slug for slug in posts)}
        if previous_manifest and previous_manifest["posts"] == {"status": 200 if blog_ok else 503, "metadata": posts} and previous_manifest["modes"] == {"status": 200 if modes_ok else 503, "metadata": modes} and set(previous_manifest["routes"]) == required:
            unchanged = all(
                previous_manifest["routes"][route]["version"] == runtime.route_version(route, posts, modes, build)
                and previous_manifest["routes"][route]["status"] == (200 if route_allowed(route, posts, blog_ok, modes_ok) else 503)
                for route in required
            )
            if unchanged:
                print(f"[publisher-capture] Metadata unchanged; reusing {previous.name}", flush=True)
                return previous
        with tempfile.TemporaryDirectory(prefix=".next-", dir=output) as temporary:
            staging = Path(temporary)
            routes = {}
            pending = []
            for route in (*runtime.ROUTES, "/blog", *("/blog/" + slug for slug in posts)):
                version = runtime.route_version(route, posts, modes, build)
                if not route_allowed(route, posts, blog_ok, modes_ok):
                    failed_route(staging, routes, route, posts, modes, build)
                    continue
                prior = previous_manifest["routes"].get(route) if previous_manifest else None
                if prior and prior["status"] == 200 and prior["version"] == version:
                    # Copy only validated unchanged HTML. No tree-wide stale fallback.
                    target = runtime.output_file(staging, route)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(runtime.output_file(previous, route), target)
                    routes[route] = dict(prior)
                else:
                    pending.append(route)
            if pending:
                try:
                    with capture_session(assets, backend, posts, timeout, modes=modes) as (server, browser):
                        for route in pending:
                            try:
                                html = browser.capture(server, route, public_origin)
                                atomic_write(runtime.output_file(staging, route), html)
                                routes[route] = {"status": 200, "version": runtime.route_version(route, posts, modes, build), "sha256": hashlib.sha256(html.encode("utf-8")).hexdigest()}
                            except Exception as error:
                                print(f"[publisher-capture] Route unavailable {route}: {error}", flush=True)
                                failed_route(staging, routes, route, posts, modes, build)
                except Exception as error:
                    # A browser launch/session failure cannot invalidate copied static pages.
                    print(f"[publisher-capture] Renderer unavailable: {error}", flush=True)
                    for route in pending:
                        if route not in routes:
                            failed_route(staging, routes, route, posts, modes, build)
            # Recheck metadata independently. Changes invalidate only dependent routes,
            # not unrelated static pages or the other API's snapshots.
            captured_posts, captured_modes = posts, modes
            posts, blog_ok, modes, modes_ok = metadata(backend, {"posts": {"metadata": captured_posts}, "modes": {"metadata": captured_modes}})
            required = {*runtime.ROUTES, "/blog", *("/blog/" + slug for slug in posts)}
            for route in set(routes) - required:
                remove_html(staging, route)
                del routes[route]
            for route in required:
                version = runtime.route_version(route, posts, modes, build)
                if not route_allowed(route, posts, blog_ok, modes_ok) or routes.get(route, {}).get("version") != version:
                    failed_route(staging, routes, route, posts, modes, build)
            if runtime.asset_fingerprint(assets) != build:
                raise runtime.PublisherError("SPA shell/assets changed while capturing; artifact was not published")
            manifest = {
                "schema": 1,
                "build_fingerprint": build,
                "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "posts": {"status": 200 if blog_ok else 503, "metadata": posts},
                "modes": {"status": 200 if modes_ok else 503, "metadata": modes},
                "routes": routes,
            }
            # Keep API order: recent/related dependencies must match the actual backend.
            atomic_write(staging / ".publisher-posts.json", json.dumps(posts, ensure_ascii=False))
            atomic_write(staging / runtime.MANIFEST, json.dumps(manifest, ensure_ascii=False))
            runtime.validate_release(staging, expected_build=build)
            release = output / ("release-" + uuid.uuid4().hex)
            staging.rename(release)
            temporary_link = output / (".current-" + uuid.uuid4().hex)
            try:
                temporary_link.symlink_to(release.name, target_is_directory=True)
                os.replace(temporary_link, output / "current")
                # Persist directory entries as well as already-fsynced HTML/manifests.
                directory_fd = os.open(output, os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            finally:
                if temporary_link.is_symlink():
                    temporary_link.unlink()
            successful = sum(item["status"] == 200 for item in routes.values())
            print(f"[publisher-capture] Published {successful} verified routes, {len(routes) - successful} unavailable routes: {release.name}", flush=True)
            return release


def main(default_assets=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets-dir", type=Path, default=default_assets or Path("/usr/share/nginx/html"))
    parser.add_argument("--output-dir", type=Path, help="Defaults to /var/run/countrydle-publisher in containers or ASSETS/publisher-snapshots for publisher:build")
    parser.add_argument("--watch", action="store_true", help="Explicit development-only refresh loop; otherwise exits after one publication")
    args = parser.parse_args()
    backend, public_origin, timeout = configuration()
    output = args.output_dir or (args.assets_dir / "publisher-snapshots" if default_assets is not None else Path("/var/run/countrydle-publisher"))
    interval = runtime.poll_interval() if args.watch else None
    while True:
        publish(args.assets_dir, output, backend, public_origin, timeout)
        if not args.watch:
            return
        time.sleep(interval)


if __name__ == "__main__":
    try:
        main()
    except (runtime.PublisherError, OSError, ValueError) as error:
        raise SystemExit(f"[publisher-capture] Failed: {error}") from error
