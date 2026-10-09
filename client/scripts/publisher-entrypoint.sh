#!/bin/sh
set -eu

# Both processes are required. A dead publisher must never leave healthy nginx
# serving an old homepage; a dead nginx must not leave an orphan capture process.
python3 /usr/local/lib/countrydle/publisher-runtime.py &
publisher_pid=$!
nginx -g 'daemon off;' &
nginx_pid=$!

shutdown() {
    trap - TERM INT
    kill -TERM "$publisher_pid" "$nginx_pid" 2>/dev/null || true
    wait "$publisher_pid" 2>/dev/null || true
    wait "$nginx_pid" 2>/dev/null || true
}
trap 'shutdown; exit 0' TERM INT

while kill -0 "$publisher_pid" 2>/dev/null && kill -0 "$nginx_pid" 2>/dev/null; do
    sleep 1 &
    wait "$!" || true
done

shutdown
exit 1
