#!/usr/bin/env bash
# LifeBoard's Docker entrypoint. Runs as root briefly to fix ownership
# on bind-mounted volumes, then drops to the unprivileged `lifeboard`
# user before exec'ing the real command.
#
# Why this exists: the Dockerfile's `chown -R lifeboard:lifeboard /app`
# only affects the image's baked-in layer at BUILD time. At RUN time,
# docker-compose.yml bind-mounts the host's ./backend/data (and
# ./config) directories on top of that path, completely replacing
# whatever ownership the image had there — whatever UID actually owns
# the host directory wins. If that's root (common on a home server
# where the repo was cloned as root, or any UID other than 1000), the
# container's non-root `lifeboard` user can't write to it and sqlite3
# fails with "unable to open database file" on every boot. Fixing
# ownership here, at every container start, makes this work regardless
# of what UID happens to own the directory on the host.

set -euo pipefail

if [ "$(id -u)" = "0" ]; then
  # Only the two bind-mounted paths — never chown the whole /app tree,
  # that would be slow and pointless for files that already shipped
  # correctly owned in the image layer.
  mkdir -p /app/backend/data /app/config
  chown -R lifeboard:lifeboard /app/backend/data /app/config
  exec gosu lifeboard "$0" "$@"
fi

exec "$@"
