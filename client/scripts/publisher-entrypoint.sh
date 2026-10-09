#!/bin/sh
set -eu

# Render only the resolver token, preserving nginx variables and other origins.
# Docker, Podman and host-managed networks supply their own DNS here.
python3 - <<'PY'
import ipaddress
from pathlib import Path

nameservers = []
for line in Path("/etc/resolv.conf").read_text(encoding="utf-8").splitlines():
    fields = line.split("#", 1)[0].split(";", 1)[0].split()
    if len(fields) < 2 or fields[0] != "nameserver":
        continue
    try:
        address = ipaddress.ip_address(fields[1])
    except ValueError:
        continue
    # nginx resolver literals cannot represent scoped IPv6 addresses.
    if address.version == 6 and address.scope_id is not None:
        continue
    value = f"[{address.compressed}]" if address.version == 6 else str(address)
    if value not in nameservers:
        nameservers.append(value)

if not nameservers:
    raise SystemExit("No usable IP nameservers found in /etc/resolv.conf")
template = Path("/etc/nginx/templates/default.conf.template").read_text(encoding="utf-8")
token = "__PUBLISHER_RESOLVERS__"
if template.count(token) != 1:
    raise SystemExit("nginx template must contain exactly one publisher resolver token")
Path("/etc/nginx/conf.d/default.conf").write_text(
    template.replace(token, " ".join(nameservers)), encoding="utf-8"
)
PY

# Both serving processes are required. A child failure shuts down its peer;
# no capture process is started, and the mounted snapshot volume stays read-only.
python3 /usr/local/lib/countrydle/publisher-runtime.py \
    --assets-dir /usr/share/nginx/html \
    --output-dir /var/run/countrydle-publisher \
    --port 8765 &
publisher_pid=$!
nginx -g 'daemon off;' &
nginx_pid=$!
sleeper_pid=

shutdown() {
    trap '' TERM INT
    if [ -n "$sleeper_pid" ]; then
        kill -TERM "$sleeper_pid" 2>/dev/null || true
        wait "$sleeper_pid" 2>/dev/null || true
    fi
    kill -TERM "$publisher_pid" "$nginx_pid" 2>/dev/null || true
    wait "$publisher_pid" 2>/dev/null || true
    wait "$nginx_pid" 2>/dev/null || true
}
trap 'shutdown; exit 143' TERM
trap 'shutdown; exit 130' INT

while kill -0 "$publisher_pid" 2>/dev/null && kill -0 "$nginx_pid" 2>/dev/null; do
    sleep 1 &
    sleeper_pid=$!
    wait "$sleeper_pid" || true
    sleeper_pid=
done

# Even a clean but unexpected child exit is a serving failure.
status=0
if ! kill -0 "$publisher_pid" 2>/dev/null; then
    wait "$publisher_pid" || status=$?
else
    wait "$nginx_pid" || status=$?
fi
if [ "$status" -eq 0 ]; then
    status=1
fi
shutdown
exit "$status"
