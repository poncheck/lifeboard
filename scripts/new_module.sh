#!/usr/bin/env bash
# LifeBoard — scaffolding generator for a new module (and optionally its
# integration half). Per docs/MODULE_AUTHORING.md: a module is a folder
# with module.json + provider.py; an integration (if the module pulls
# from a third-party API) follows the same pattern with
# integration.json + sync.py.
#
# Usage:
#   scripts/new_module.sh <module_id> [--with-integration]
#
# Creates:
#   backend/modules/<module_id>/{module.json,provider.py}
#   backend/integrations/<module_id>/{integration.json,sync.py}   (if --with-integration)
#
# All generated files are stubs with TODOs and the exact method
# signatures from backend/core/base.py — fill them in, then restart the
# container (or use the admin panel's reload action in dev) to pick
# them up.

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <module_id> [--with-integration]" >&2
  exit 1
fi

MODULE_ID="$1"
WITH_INTEGRATION=false
if [ "${2:-}" = "--with-integration" ]; then
  WITH_INTEGRATION=true
fi

if ! [[ "$MODULE_ID" =~ ^[a-z][a-z0-9_]*$ ]]; then
  echo "Error: module_id must be lowercase snake_case (e.g. 'my_module'), matching the folder name LifeBoard will discover it under." >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODULE_DIR="$REPO_ROOT/backend/modules/$MODULE_ID"

if [ -e "$MODULE_DIR" ]; then
  echo "Error: $MODULE_DIR already exists." >&2
  exit 1
fi

mkdir -p "$MODULE_DIR"

cat > "$MODULE_DIR/module.json" << EOF
{
  "id": "$MODULE_ID",
  "name": "TODO: Display Name",
  "description": "TODO: one-sentence description of what this card shows.",
  "icon": "activity",
  "category": "life",
  "default_refresh_seconds": 60,
  "grid_size": "1x1",
  "requires_integration": $([ "$WITH_INTEGRATION" = true ] && echo "\"$MODULE_ID\"" || echo "null")
}
EOF

cat > "$MODULE_DIR/provider.py" << EOF
"""TODO: one-line description of what this module displays.

See docs/MODULE_AUTHORING.md for the full contract. Key rule:
get_data() must NEVER raise — catch your own errors and return
{"error": "..."} so a bug here can't take down the whole dashboard.
"""
from backend.core.base import DashboardModule


class Provider(DashboardModule):
    def get_data(self, db) -> dict:
        try:
            # TODO: read from your own table(s) in \`db\` (a raw
            # sqlite3.Connection) — never make a network call here,
            # that's the integration's job (sync.py, if you have one).
            row = None
        except Exception:
            row = None

        if row is None:
            return {
                "title": "TODO: Display Name",
                "primary_value": "no data yet",
                "status": "neutral",
            }

        # TODO: shape your real data into the generic card schema:
        # https://github.com/poncheck/lifeboard/blob/main/docs/ARCHITECTURE.md#the-generic-card-schema
        return {
            "title": "TODO: Display Name",
            "primary_value": "TODO",
            "status": "ok",
        }
EOF

echo "Created $MODULE_DIR/{module.json,provider.py}"

if [ "$WITH_INTEGRATION" = true ]; then
  INTEGRATION_DIR="$REPO_ROOT/backend/integrations/$MODULE_ID"

  if [ -e "$INTEGRATION_DIR" ]; then
    echo "Error: $INTEGRATION_DIR already exists." >&2
    exit 1
  fi

  mkdir -p "$INTEGRATION_DIR"

  cat > "$INTEGRATION_DIR/integration.json" << EOF
{
  "id": "$MODULE_ID",
  "name": "TODO: Platform Name",
  "description": "TODO: what this pulls and why.",
  "credential_fields": [
    {"key": "api_key", "label": "API Key", "secret": true}
  ],
  "sync_interval_seconds": 900
}
EOF

  cat > "$INTEGRATION_DIR/sync.py" << EOF
"""TODO: one-line description of what platform this syncs from.

See docs/MODULE_AUTHORING.md for the full contract. Key rules:
- test_connection() is a cheap, read-only check — must not write data.
- sync() may raise on real failures (bad credentials, network error,
  platform outage) — the registry catches it, logs it, and reports
  the error for the admin panel's status line. Don't swallow your own
  exceptions just to be "safe"; that hides real failures.
- Upsert, not insert — sync() runs on a schedule, syncing the same
  data twice must not create duplicate rows.
- Own your own tables — never write into another integration's tables
  or a core LifeBoard table.
"""
from backend.core.base import Integration


class Sync(Integration):
    def test_connection(self, credentials: dict) -> bool:
        api_key = credentials.get("api_key")
        if not api_key:
            return False
        try:
            # TODO: one cheap, read-only call to the platform.
            return True
        except Exception:
            return False

    def sync(self, credentials: dict, db) -> None:
        api_key = credentials.get("api_key")
        if not api_key:
            return

        # TODO: fetch from the platform (raising on failure is fine).
        # rows = fetch_from_platform(api_key)

        db.execute(
            "CREATE TABLE IF NOT EXISTS ${MODULE_ID}_data "
            "(id TEXT PRIMARY KEY, value REAL)"
        )
        # TODO: upsert normalized rows, e.g.:
        # for row in rows:
        #     db.execute(
        #         "INSERT INTO ${MODULE_ID}_data (id, value) VALUES (?, ?) "
        #         "ON CONFLICT(id) DO UPDATE SET value = excluded.value",
        #         (row["id"], row["value"]),
        #     )
        db.commit()
EOF

  echo "Created $INTEGRATION_DIR/{integration.json,sync.py}"
fi

echo ""
echo "Next steps:"
echo "  1. Fill in the TODOs above."
echo "  2. Restart the container (or use the admin panel's reload action in dev)."
echo "  3. Enable '$MODULE_ID' from the dashboard's Configure panel."
if [ "$WITH_INTEGRATION" = true ]; then
  echo "  4. Enter credentials for '$MODULE_ID' in Admin -> Integrations, then 'Sync now'."
fi
echo ""
echo "See docs/MODULE_AUTHORING.md for the full walkthrough and contribution checklist."
