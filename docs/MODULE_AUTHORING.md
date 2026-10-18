# Writing Your Own Module

This is the hands-on walkthrough. For the full design rationale (why the integration/display-provider split exists, the generic card schema, discovery rules) read [`ARCHITECTURE.md`](ARCHITECTURE.md) first — this doc assumes you've skimmed it.

## The four files

A module backed by a third-party platform has **two halves**, each its own folder:

```
backend/integrations/<integration_id>/
├── integration.json      # manifest: credential fields, sync interval
└── sync.py                # class Sync(Integration): test_connection(), sync()

backend/modules/<module_id>/
├── module.json            # manifest: display metadata, requires_integration
└── provider.py            # class Provider(DashboardModule): get_data()
```

A module with **no third-party data source** (like the built-in `clock`, or `nutrition`'s manual-entry form) only needs the `backend/modules/` half — set `"requires_integration": null` in `module.json` and skip the integration folder entirely.

`integration_id` and `module_id` don't have to match (a module can read data another module's integration already synced), but for a typical one-integration-feeds-one-module pair, using the same id for both keeps the folders easy to find.

## Example 1: a display-only module (no integration)

The simplest possible module — shows a static-ish value, nothing to sync. This is literally the built-in `echo` module's shape minus the integration (see Example 2 for the full pair):

**`backend/modules/hello/module.json`**
```json
{
  "id": "hello",
  "name": "Hello",
  "description": "A friendly greeting.",
  "icon": "smile",
  "category": "system",
  "default_refresh_seconds": 3600,
  "grid_size": "1x1",
  "requires_integration": null
}
```

**`backend/modules/hello/provider.py`**
```python
from datetime import datetime, timezone
from backend.core.base import DashboardModule

class Provider(DashboardModule):
    def get_data(self, db) -> dict:
        return {
            "title": "Hello",
            "primary_value": "👋",
            "status": "ok",
            "lines": [{"label": "Greeting", "value": "Hi there!"}],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
```

Drop those two files in, restart the container (or hit the admin panel's reload action in dev), enable "Hello" in the config panel. Done — no frontend code, the generic card renderer handles it.

## Example 2: an integration + module pair

The built-in `echo` integration/module pair is the canonical copy-pasteable example — a fake "platform" that just echoes back whatever credential you type, exercising the full lifecycle (save credentials → test → sync → display) without needing a real third-party account. Read the actual source, it's short:

- [`backend/integrations/echo/integration.json`](../backend/integrations/echo/integration.json) + [`sync.py`](../backend/integrations/echo/sync.py)
- [`backend/modules/echo/module.json`](../backend/modules/echo/module.json) + [`provider.py`](../backend/modules/echo/provider.py)

The shape, annotated:

**`integration.json`** — `credential_fields` drives the admin panel's auto-generated form (no frontend code needed per integration); `secret: true` fields are masked and always encrypted at rest.
```json
{
  "id": "my_platform",
  "name": "My Platform",
  "description": "What this pulls and why.",
  "credential_fields": [
    {"key": "api_key", "label": "API Key", "secret": true}
  ],
  "sync_interval_seconds": 900
}
```

**`sync.py`** — `test_connection()` is a cheap read-only check for the admin panel's "Test & Save" button; `sync()` does the real work. Raising from either is fine and expected for real failures (bad credentials, network error, platform outage) — the registry catches it, logs it, and reports `(success, error_message)` for the admin panel's status line and the scheduler's retry-next-tick logic. Don't swallow exceptions yourself just to be "safe"; that hides real failures instead of surfacing them.
```python
from backend.core.base import Integration

class Sync(Integration):
    def test_connection(self, credentials: dict) -> bool:
        api_key = credentials.get("api_key")
        if not api_key:
            return False
        try:
            # one cheap read-only call to the platform
            return True
        except Exception:
            return False

    def sync(self, credentials: dict, db) -> None:
        api_key = credentials.get("api_key")
        if not api_key:
            return
        # fetch from the platform (let real failures raise — see above)
        rows = fetch_from_platform(api_key)

        db.execute(
            "CREATE TABLE IF NOT EXISTS my_platform_data "
            "(id TEXT PRIMARY KEY, value REAL)"
        )
        for row in rows:
            db.execute(
                "INSERT INTO my_platform_data (id, value) VALUES (?, ?) "
                "ON CONFLICT(id) DO UPDATE SET value = excluded.value",
                (row["id"], row["value"]),
            )
        db.commit()
```

Rules that matter here:
- **Own your own tables.** Don't write into another integration's tables or a core LifeBoard table. Prefix table names with your integration id if there's any ambiguity.
- **Upsert, not insert.** `sync()` runs on a schedule — syncing the same data twice must not create duplicate rows. Pick a natural key (a date, a platform-assigned id) and `ON CONFLICT ... DO UPDATE`.
- **`sync()` gets a raw `sqlite3.Connection`**, not an ORM — write plain SQL.

**`module.json`** — `requires_integration` greys the module out in the config panel (with a link to Admin → Integrations) until that integration has credentials saved. `grid_size` is a hint (`"1x1"`, `"2x1"`, `"2x2"`) for the responsive grid.
```json
{
  "id": "my_module",
  "name": "My Module",
  "description": "What this shows.",
  "icon": "activity",
  "category": "life",
  "default_refresh_seconds": 300,
  "grid_size": "1x1",
  "requires_integration": "my_platform"
}
```

**`provider.py`** — the opposite error-handling rule from `sync()`: `get_data()` must **never raise**. Catch your own errors and return `{"error": "..."}` — the generic renderer shows that as a clean error card instead of crashing the whole dashboard.
```python
from backend.core.base import DashboardModule

class Provider(DashboardModule):
    def get_data(self, db) -> dict:
        try:
            row = db.execute(
                "SELECT value FROM my_platform_data ORDER BY id DESC LIMIT 1"
            ).fetchone()
        except Exception:
            row = None  # table doesn't exist yet — no sync has run

        if row is None:
            return {"title": "My Module", "primary_value": "no data yet", "status": "neutral"}
        return {"title": "My Module", "primary_value": str(row[0]), "status": "ok"}
```

## The generic card schema

Any `get_data()` returning this shape renders automatically, zero frontend code:

```json
{
  "title": "My Module",
  "primary_value": "72",
  "primary_unit": "%",
  "status": "ok",
  "lines": [{"label": "Detail", "value": "some value"}],
  "updated_at": "2026-10-18T09:00:00+02:00"
}
```

| Field | Notes |
|---|---|
| `status` | `"ok"` \| `"warn"` \| `"alert"` \| `"neutral"` — drives the card's left-border accent color |
| `lines` | optional array of `{label, value}` secondary rows |
| `updated_at` | optional ISO 8601 string, rendered as "updated Xm ago" |

A module needing something the generic card can't express (a live-ticking clock, a log-a-meal form) ships a custom frontend renderer instead — see the next section.

## Custom frontend renderers (only if you need one)

Most modules don't need this — the generic card above covers status displays fine. If yours does (an inline form, a live-updating element that shouldn't poll the backend every second), add `frontend/src/widgets/<module_id>.js` exporting an object with a `render(container, data)` method, and register it in `frontend/src/widgets/registry.js`'s `_custom` map. The built-in `clock` (live tick, no polling) and `nutrition` (inline log-a-meal form) modules are the two real examples — read `frontend/src/widgets/clock.js` and `frontend/src/widgets/nutrition.js`.

## Testing locally

1. Drop your two (or four) files into `backend/modules/` (and `backend/integrations/` if applicable).
2. `docker compose up` (or run `uvicorn backend.main:create_app --factory` directly against your dev checkout).
3. Log in, open the config panel, enable your module.
4. If it has an integration: open Admin → Integrations, fill in the credential form, "Test & Save", then "Sync now" to populate real data without waiting for the schedule.
5. A broken `module.json`/`integration.json` or an import error in your `.py` file is logged and the module/integration is silently skipped — check the container logs if something you dropped in doesn't show up in `/api/modules` or `/api/integrations`.

### Writing tests

Not required to make the module work, but strongly recommended before contributing back (see the checklist below). Look at `backend/tests/test_echo_builtin.py` and `backend/tests/test_weather.py` for the pattern: instantiate `Sync`/`Provider` directly with an in-memory `sqlite3.connect(":memory:")`, mock `urllib.request.urlopen` if your integration makes network calls (see `backend/tests/test_intervals_icu.py` for the mocking pattern), and assert both the happy path and the "no sync has run yet" / "sync raises" degraded paths.

## Contributing your module back

If you want your module merged into the main LifeBoard repo (rather than just keeping it in your own fork):

- [ ] Both halves follow the rules above: `sync()` can raise on real failures, `get_data()` never does; upserts are idempotent; no cross-module/cross-integration table writes.
- [ ] `credential_fields` labels are clear enough that someone who's never seen your integration's API can fill in the form correctly.
- [ ] Tests cover: discovery (the manifest is valid JSON, the class is found), the happy path, and at least one degraded path (no sync yet / sync failure).
- [ ] If your integration depends on a third-party account most users won't have (like `training_readiness`'s `intervals_icu` dependency), that's fine — it just means your module's "happy path" test should still pass in CI without real credentials (mock the network call).
- [ ] Open a PR. CI (`.github/workflows/ci.yml`) runs the full backend test suite automatically.
