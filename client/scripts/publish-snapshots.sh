#!/usr/bin/env bash
# Usage: bash publish-snapshots.sh CAPTURE_OUTPUT_DIR [STANDALONE_RUNTIME_VALIDATOR]
# Requires the mounted host directory, Python 3 + rsync on both hosts, and an SSH
# account allowed to write it and exec the explicitly configured Docker/Podman
# serving container. Supply key/known_hosts contents via env, not image layers.
set +x
set -euo pipefail
umask 077

fail() { printf 'Publisher promotion failed: %s\n' "$1" >&2; exit 1; }
[[ $# -ge 1 && $# -le 2 ]] || fail 'usage: publish-snapshots.sh CAPTURE_OUTPUT_DIR [STANDALONE_RUNTIME_VALIDATOR]'
for name in PUBLISHER_SSH_HOST PUBLISHER_SSH_USER PUBLISHER_SSH_KEY PUBLISHER_SSH_KNOWN_HOSTS PUBLISHER_REMOTE_DIR PUBLISHER_CONTAINER_ENGINE PUBLISHER_FRONTEND_CONTAINER; do
    [[ -n ${!name:-} ]] || fail "required deployment setting $name is missing"
done
for command in python3 ssh ssh-keygen rsync mktemp; do
    command -v "$command" >/dev/null || fail "required command $command is not installed"
done
host=$PUBLISHER_SSH_HOST
user=$PUBLISHER_SSH_USER
remote=$PUBLISHER_REMOTE_DIR
engine=$PUBLISHER_CONTAINER_ENGINE
frontend=$PUBLISHER_FRONTEND_CONTAINER
[[ $engine == docker || $engine == podman ]] || fail 'PUBLISHER_CONTAINER_ENGINE must explicitly select docker or podman on the SSH host'
[[ $frontend =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]*$ ]] || fail 'PUBLISHER_FRONTEND_CONTAINER must identify the actual deployed serving container by safe name or ID'
port=${PUBLISHER_SSH_PORT:-22}
[[ $user =~ ^[a-zA-Z_][a-zA-Z0-9_-]*$ ]] || fail 'PUBLISHER_SSH_USER is not a valid SSH account name'
[[ $host =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]*$ || $host =~ ^[a-fA-F0-9:]+$ ]] || fail 'PUBLISHER_SSH_HOST must be a hostname or IP address, without user, port or shell syntax'
[[ $port =~ ^[0-9]{1,5}$ ]] || fail 'PUBLISHER_SSH_PORT must be an integer from 1 to 65535'
port=$((10#$port))
((port >= 1 && port <= 65535)) || fail 'PUBLISHER_SSH_PORT must be an integer from 1 to 65535'
[[ $remote =~ ^/[a-zA-Z0-9_./-]+$ && $remote != / ]] || fail 'PUBLISHER_REMOTE_DIR must be an absolute, non-root path using letters, digits, underscore, dot, slash or hyphen'
[[ /${remote#/}/ != *'/../'* && /${remote#/}/ != *'/./'* ]] || fail 'PUBLISHER_REMOTE_DIR must not contain dot or parent path segments'
remote=${remote%/}
python3 - "$host" "$remote" <<'PY'
import ipaddress
import re
import sys
host, remote = sys.argv[1:]
try:
    ipaddress.ip_address(host)
except ValueError:
    labels = host.rstrip('.').split('.')
    if len(host) > 253 or not all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label) for label in labels):
        raise SystemExit('PUBLISHER_SSH_HOST must be a valid hostname or IP address')
if remote.strip('/') == '' or any(segment in ('.', '..') for segment in remote.split('/')):
    raise SystemExit('PUBLISHER_REMOTE_DIR must be a non-root absolute path without dot/parent segments')
PY

validator=${2:-$(dirname -- "${BASH_SOURCE[0]}")/publisher-runtime.py}
[[ -f $validator ]] || fail 'standalone publisher-runtime.py validator is missing'
# Resolve only the worker-owned current -> release-<uuid> link. Never upload a
# mutable capture directory, a link outside the artifact, or incomplete output.
release=$(python3 - "$1" <<'PY'
import pathlib
import re
import sys
root = pathlib.Path(sys.argv[1]).resolve(strict=True)
current = root / 'current'
if not current.is_symlink():
    raise SystemExit('Capture output must contain its atomic current symlink')
release = current.resolve(strict=True)
if release.parent != root or not re.fullmatch(r'release-[0-9a-f]{32}', release.name) or not release.is_dir():
    raise SystemExit('Capture current must select an immutable release-<uuid> directly inside output')
# A snapshot is data, not executable/link content. Do not transmit links that
# could escape staging or cause validation to follow unrelated host files.
if any(path.is_symlink() or not (path.is_file() or path.is_dir()) for path in release.rglob('*')):
    raise SystemExit('Capture release contains a symlink or special file')
print(release)
PY
) || fail 'capture output is not a complete immutable release'
python3 "$validator" --validate-release "$release" || fail 'local snapshot manifest/content validation failed'
release_name=$(basename -- "$release")
# A separate per-attempt name permits retrying the same artifact after a failed
# upload without ever editing an already promoted immutable release.
attempt=$(python3 -c 'import uuid; print(uuid.uuid4().hex)')
staging="$remote/.incoming-$attempt"
work=$(mktemp -d /tmp/countrydle-publish.XXXXXXXX)
prepared=false
phase='SSH configuration'

ssh_run() { "$work/ssh" "$user@$host" "$@"; }
cleanup() {
    status=$?
    trap - EXIT
    if [[ $prepared == true ]]; then
        # Cleanup only our staging path; current and prior releases are untouched.
        ssh_run python3 - "$staging" <<'PY' >/dev/null 2>&1 || true
import pathlib
import shutil
import sys
path = pathlib.Path(sys.argv[1])
if path.name.startswith('.incoming-') and not path.is_symlink():
    shutil.rmtree(path, ignore_errors=True)
PY
    fi
    rm -rf -- "$work"
    if ((status != 0)); then
        printf 'Publisher promotion failed during %s; previous release was not modified before successful atomic promotion.\n' "$phase" >&2
    fi
    exit "$status"
}
trap cleanup EXIT
printf '%s\n' "$PUBLISHER_SSH_KEY" > "$work/key"
printf '%s\n' "$PUBLISHER_SSH_KNOWN_HOSTS" > "$work/known_hosts"
unset PUBLISHER_SSH_KEY PUBLISHER_SSH_KNOWN_HOSTS
ssh-keygen -y -P '' -f "$work/key" >/dev/null 2>&1 || fail 'PUBLISHER_SSH_KEY must contain a valid unencrypted deployment private key'
ssh-keygen -l -f "$work/known_hosts" >/dev/null 2>&1 || fail 'PUBLISHER_SSH_KNOWN_HOSTS must contain valid pinned host keys'
# Fixed generated wrapper also gives rsync exactly the strict SSH options.
cat > "$work/ssh" <<EOF
#!/usr/bin/env bash
exec ssh -F /dev/null -p "$port" \\
  -o BatchMode=yes -o IdentitiesOnly=yes -o IdentityAgent=none \\
  -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no \\
  -o StrictHostKeyChecking=yes -o UpdateHostKeys=no \\
  -o GlobalKnownHostsFile=/dev/null -o UserKnownHostsFile="$work/known_hosts" \\
  -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \\
  -i "$work/key" "\$@"
EOF
chmod 700 "$work/ssh"

phase='remote staging setup'
ssh_run python3 - "$remote" "$staging" <<'PY'
import os
import pathlib
import sys
root, staging = map(pathlib.Path, sys.argv[1:])
if not root.is_dir() or not os.access(root, os.W_OK | os.X_OK):
    raise SystemExit('PUBLISHER_REMOTE_DIR must already exist and be writable by the configured SSH account; provision the frontend bind mount first')
if (root / 'current').exists() and not (root / 'current').is_symlink():
    raise SystemExit('Remote current exists but is not the publisher symlink')
for directory in (staging, staging / 'release'):
    directory.mkdir(mode=0o755)
    directory.chmod(0o755)  # Container must traverse staging through its RO mount.
# The reader opens this existing synchronization file readonly, never creates it.
descriptor = os.open(root / '.promotion.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o644)
try:
    os.fchmod(descriptor, 0o644)
finally:
    os.close(descriptor)
PY
prepared=true
phase='snapshot upload'
rsync_host=$host
[[ $host != *:* ]] || rsync_host="[$host]"
# No --inplace, no updates to current, and no deletion of prior releases. An
# interrupted transfer can leave only an unreferenced .incoming-* directory.
rsync --recursive --times --perms --quiet --chmod=D755,F644 \
    --rsh="$work/ssh" -- "$release/" "$user@$rsync_host:$staging/release/"
rsync --quiet --rsh="$work/ssh" -- "$validator" "$user@$rsync_host:$staging/validator.py"
phase='remote content validation'
ssh_run python3 "$staging/validator.py" --validate-release "$staging/release"
phase='deployed bundle validation and atomic release promotion'
ssh_run python3 - "$remote" "$staging" "$release_name" "$attempt" "$engine" "$frontend" <<'PY'
import fcntl
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
root, staging = (pathlib.Path(value).resolve(strict=True) for value in sys.argv[1:3])
name, attempt, engine, frontend = sys.argv[3:]
release = root / name
link = root / ('.current-' + attempt)
manifest_name = '.publisher-manifest.json'

def serving_container():
    if shutil.which(engine) is None:
        raise SystemExit(f'Configured PUBLISHER_CONTAINER_ENGINE {engine} is not installed for the SSH account')
    result = subprocess.run([engine, 'inspect', '--', frontend], text=True, capture_output=True)
    try:
        containers = json.loads(result.stdout)
        container = containers[0] if len(containers) == 1 else {}
        identifier = container.get('Id')
        running = container.get('State', {}).get('Running') is True
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        identifier, running = None, False
    if result.returncode != 0 or not running or not isinstance(identifier, str) or not re.fullmatch(r'[0-9a-f]{12,64}', identifier):
        raise SystemExit('PUBLISHER_FRONTEND_CONTAINER is unavailable/not running or the SSH account cannot inspect it with the configured engine')
    return identifier

def validate_deployed(identifier):
    # Inspect pins the real running container, not a guessed image/fingerprint.
    # Incoming is visible under the frontend's existing readonly snapshot mount.
    subprocess.run([
        engine, 'exec', '--', identifier, 'python3',
        '/usr/local/lib/countrydle/publisher-runtime.py',
        '--validate-release', '/var/run/countrydle-publisher/' + staging.name + '/release',
        '--assets-dir', '/usr/share/nginx/html',
    ], check=True)
    return json.loads((staging / 'release' / manifest_name).read_text())['build_fingerprint']

def retire_archives(current, previous, verified_build):
    """Keep current, two compatible archives, and every live reader's lease."""
    archives = sorted(
        (path for path in root.iterdir() if path != current and re.fullmatch(r'release-[0-9a-f]{32}', path.name)),
        key=lambda path: (path == previous, path.lstat().st_mtime),
        reverse=True,
    )
    retained = 0
    for path in archives:
        if path.is_symlink() or not path.is_dir():
            path.unlink()
            continue
        lease = None
        try:
            try:
                lease = (path / manifest_name).open('rb')
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                # Any reader still serving this immutable release must retain it,
                # even across a frontend bundle change. Exit/switch drops its SH.
                continue
            except FileNotFoundError:
                pass  # A manifest-less archive cannot have been loaded.
            compatible = False
            if lease is not None and retained < 2:
                try:
                    compatible = json.load(lease).get('build_fingerprint') == verified_build and subprocess.run(
                        [sys.executable, str(staging / 'validator.py'), '--validate-release', str(path)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    ).returncode == 0
                except (ValueError, AttributeError):
                    pass
            if compatible:
                retained += 1
            else:
                # EX on this manifest plus EX on .promotion.lock excludes both
                # existing readers and resolve/open/validate of a new reader.
                shutil.rmtree(path)
        finally:
            if lease is not None:
                lease.close()

def content_identity(directory):
    """Compare immutable data, not transport-dependent timestamps/modes."""
    digest = hashlib.sha256()
    for path in sorted(directory.rglob('*')):
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise SystemExit('Existing immutable release contains a link or special file')
        digest.update(path.relative_to(directory).as_posix().encode() + b'\0')
        digest.update(b'directory\0' if path.is_dir() else b'file\0')
        if path.is_file():
            file_digest = hashlib.sha256()
            with path.open('rb') as source:
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    file_digest.update(block)
            digest.update(file_digest.digest())
    return digest.digest()

# Shared reader locks prevent resolve/open from racing deletion; lifetime SH
# manifest leases independently protect readers still using an older release.
with (root / '.promotion.lock').open('r+') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    if os.path.lexists(root / 'current') and not (root / 'current').is_symlink():
        raise SystemExit('Remote current is not a publisher symlink')
    previous = (root / 'current').resolve(strict=True) if (root / 'current').is_symlink() else None
    if previous is not None and (previous.parent != root or not re.fullmatch(r'release-[0-9a-f]{32}', previous.name)):
        raise SystemExit('Remote current is not a safe immutable publisher release')
    identifier = serving_container()
    verified_build = validate_deployed(identifier)
    already_current = previous == release
    if release.exists() or release.is_symlink():
        if release.is_symlink() or not release.is_dir():
            raise SystemExit('Immutable release exists but is not a real directory')
        if content_identity(release) != content_identity(staging / 'release'):
            raise SystemExit('Immutable release UUID has conflicting content; refusing to overwrite it')
    # A container replacement during validation must fail before current changes,
    # including the otherwise-idempotent path.
    if serving_container() != identifier:
        raise SystemExit('Deployed serving container changed during validation; current was preserved')
    if not release.exists():
        (staging / 'release').rename(release)
    release.chmod(0o755)
    if not already_current:
        try:
            link.symlink_to(name, target_is_directory=True)
            os.replace(link, root / 'current')
        finally:
            if os.path.lexists(link):
                link.unlink()
    try:
        retire_archives(release, previous, verified_build)
    except OSError as error:
        # Promotion is already complete; never evict current to fix retirement.
        print(f'Publisher snapshot valid/current; archive retirement deferred: {error}', file=sys.stderr)
print('Identical validated publisher snapshot already current' if already_current else 'Validated publisher snapshot atomically promoted')
PY
