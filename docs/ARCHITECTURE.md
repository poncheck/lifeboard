# LifeBoard Architecture

This document is the source of truth for how LifeBoard's plugin system works. If you're adding a module or integration, read this first; the step-by-step walkthrough lives in [`MODULE_AUTHORING.md`](MODULE_AUTHORING.md).

## The big picture

```
┌─────────────┐      sync()       ┌──────────────────┐     get_data()    ┌──────────────┐
│ Third-party  │ ───────────────> │  LifeBoard's own  │ <───────────────  │  Dashboard    │
│ platform API │                  │  SQLite database  │                   │  module card  │
│ (Intervals,  │                  │  (backend/data/)  │                   │  (frontend)   │
│  Traccar...) │                  └──────────────────┘                   └──────────────┘
└─────────────┘
      ^
      | credentials (encrypted, admin panel)
      |
 ┌──────────┐
 │   You     │
 └──────────┘
```

A **module has two optional halves**:

1. **Integration** — pulls data from a third-party platform on a schedule, writes it into LifeBoard's own database. Needs credentials (API key, server URL, etc.), configured through the admin panel.
2. **Display provider** — reads from LifeBoard's own database and returns a small JSON payload that renders as a card.

Some modules only need the second half (the built-in `clock` module needs no integration — there's nothing to sync, it's just the current time). Modules backed by a third-party platform need both.

**Why the split?** Keeping integrations and display providers separate means:
- A module never talks to a third-party API directly — it can't, because `get_data()` only gets a database handle, not network access. This keeps rendering fast (no API latency in the request path) and means one slow/down platform never blocks the dashboard from loading.
- Credentials live in exactly one place (the integration's `sync.py`), never duplicated across modules that happen to use the same platform.
- You can write a dashboard module against data LifeBoard already has (e.g. a second module reading the same Intervals.icu sync data differently) without re-implementing the API client.

## Integration contract

A folder under `backend/integrations/<integration_id>/`:

**`integration.json`**
```json
{
  "id": "intervals_icu",
  "name": "Intervals.icu",
  "description": "Training load, HRV, and activity data",
  "credential_fields": [
    {"key": "api_key", "label": "API Key", "secret": true}
  ],
  "sync_interval_seconds": 900
}
```

- `credential_fields` drives the admin panel's auto-generated form — no frontend code needed per integration.
- `secret: true` fields are masked in the UI and always encrypted at rest.

**`sync.py`**
```python
from backend.core.base import Integration

class Sync(Integration):
    def test_connection(self, credentials: dict) -> bool:
        """Called from the admin panel's 'Test & Save' button. Cheap,
        read-only check that the credentials actually work. Must not
        write any data."""
        ...

    def sync(self, credentials: dict, db) -> None:
        """Called on integration.json's sync_interval_seconds by the
        scheduler, and on-demand via the admin panel's 'Sync now' button.
        Fetch from the platform, upsert normalized rows into this
        integration's own tables in LifeBoard's database (via `db`).

        Rules:
        - Must not raise. Catch your own errors, log them, return. The
          scheduler will retry on the next tick; one broken integration
          must never crash the app or block other integrations.
        - Must be idempotent — syncing the same data twice should not
          create duplicate rows (upsert on a natural key, not insert).
        - Own your own tables. Don't write into another integration's
          tables or any core LifeBoard table.
        """
        ...
```

## Display provider contract

A folder under `backend/modules/<module_id>/`:

**`module.json`**
```json
{
  "id": "training_readiness",
  "name": "Training Readiness",
  "description": "Daily readiness score from HRV, sleep, and training load",
  "icon": "activity",
  "category": "health",
  "default_refresh_seconds": 60,
  "grid_size": "2x1",
  "requires_integration": "intervals_icu"
}
```

- `requires_integration`: if set, the config panel greys this module out (with a link to Admin → Integrations) until that integration has credentials saved and has synced at least once. `null` means the module needs no integration (e.g. `clock`).
- `grid_size`: a rough hint (`"1x1"`, `"2x1"`, `"2x2"`) for how much space the card wants in the responsive grid.

**`provider.py`**
```python
from backend.core.base import DashboardModule

class Provider(DashboardModule):
    def get_data(self, db) -> dict:
        """Called on each refresh tick by the frontend's poll loop (via
        GET /api/modules/{id}/data). Read from LifeBoard's own database —
        never make a network call here, that's the integration's job.

        Return a dict matching the generic card schema below, unless this
        module ships a custom frontend renderer.

        Rules:
        - Must be fast. Target under 200ms; the manifest's
          default_refresh_seconds assumes this isn't doing real work.
        - Must not raise. Catch your own errors and return
          {"error": "human-readable message"} — the generic renderer
          shows this as a card in an error state instead of crashing
          the whole dashboard.
        """
        ...
```

## The generic card schema

Any `get_data()` can return this shape and it renders automatically — zero frontend code required:

```json
{
  "title": "Training Readiness",
  "primary_value": "72",
  "primary_unit": "%",
  "status": "ok",
  "lines": [
    {"label": "HRV", "value": "58 ms"},
    {"label": "Sleep", "value": "7h 20m"}
  ],
  "updated_at": "2026-10-18T09:00:00+02:00"
}
```

| Field | Type | Notes |
|---|---|---|
| `title` | string | Card header |
| `primary_value` | string | The headline number/text |
| `primary_unit` | string, optional | Unit shown next to `primary_value` |
| `status` | `"ok"` \| `"warn"` \| `"alert"` \| `"neutral"` | Drives the card's accent color |
| `lines` | array of `{label, value}`, optional | Secondary detail rows |
| `updated_at` | ISO 8601 string | Shown as "updated Xm ago" |

A module that needs something the generic card can't express (the `clock` module, which needs a live local tick rather than polling every second) ships a custom renderer instead — see [Frontend widget contract](#frontend-widget-contract).

## Discovery

- `backend/core/module_registry.py` scans `backend/modules/*/module.json` at startup and on an admin "reload" action.
- `backend/core/integration_registry.py` does the same for `backend/integrations/*/integration.json`.
- Each imports its sibling Python file (`provider.py` or `sync.py`) and registers the class found there.
- **A broken manifest or an import error is logged and that one module/integration is skipped — the registry never lets one bad folder take down the whole app.** This is the load-bearing rule of an "anyone can drop a module in" system; don't weaken it.

## API surface

| Route | Auth | Purpose |
|---|---|---|
| `GET /api/account/status` | none | `{has_account}` — frontend uses this to route between setup/login/dashboard |
| `POST /api/setup` | none (locks after first success) | One-time onboarding: name, DOB, email, admin password |
| `POST /api/login` | none | `{email, password, remember_me}` → session cookie |
| `POST /api/logout` | session | Clears session cookie |
| `POST /api/account/change-password` | session | `{current_password, new_password}` — verifies current, then invalidates every session (including this one) via `session_epoch` |
| `POST /api/account/logout-all-sessions` | session | Invalidates every session token without touching the password |
| `GET /api/integrations` | session | List discovered integrations, manifests, `configured`/`last_synced_at`/`last_error` |
| `POST /api/integrations/{id}/credentials` | session | Save credentials (runs `test_connection()` first), (re)schedules sync |
| `DELETE /api/integrations/{id}/credentials` | session | Remove credentials, stop scheduled sync |
| `POST /api/integrations/{id}/sync-now` | session | Trigger an immediate sync outside the schedule |
| `GET /api/modules` | session | List discovered modules, each flagged with `requirement_satisfied` |
| `GET /api/modules/{id}/data` | session | Live data for one module (the frontend poll loop hits this) |
| `GET /api/dashboard` | session | Saved layout |
| `POST /api/dashboard` | session | Save a new layout |
| `POST /api/nutrition/entries` | session | Log a meal (kcal/protein/carbs/fat) — the `nutrition` module's manual-entry half, no integration involved |
| `GET /api/nutrition/entries` | session | Today's logged meals, newest first |
| `GET /healthz` | none | Container healthcheck |

## Frontend widget contract

- `frontend/src/widgets/generic.js` renders the schema above — every module gets this for free. It also renders an integration's own "synced Xm ago" / "sync error: ..." status directly on the card (via `data._integrationStatus`, set by `dashboard.js` from `/api/modules`' `integration_last_synced_at`/`integration_last_error`), not just in the admin panel.
- A module can ship `frontend/src/widgets/<module_id>.js` exporting a custom render function. `frontend/src/widgets/registry.js` checks for a custom renderer first, falls back to `generic.js`.
- The dashboard polls `GET /api/modules/{id}/data` on an independent `setInterval` per widget (using `refresh_seconds` from the saved layout, falling back to the manifest default) — one slow module's poll never blocks another's. The config panel (`frontend/src/config_panel.js`) exposes a per-module refresh override input alongside the enable/disable checkbox.
- Dashboard cards are drag-to-reposition (`frontend/src/dashboard.js`'s `_wireDragReorder`); dropping a card persists the new `position` order to `/api/dashboard` immediately.
- `frontend/src/theme.js` applies a `data-theme="light"` attribute on `<html>` (default is dark) and persists the choice in `localStorage`, independent of the OS's `prefers-color-scheme` — loaded in every page's `<head>` before the stylesheet to avoid a flash of the wrong theme.
- The admin panel (`frontend/src/admin/integrations.js`) renders one card per discovered integration: a form built from `credential_fields`, "Test & Save", a sync status line, and "Sync now".

## Security model (v1)

- Single operator account, set up once on first boot. No multi-user, no OAuth.
- Session via a signed, HTTP-only cookie. No auth on `/healthz` (container healthcheck needs to work before login exists).
- Integration credentials are encrypted at rest (Fernet) using a key derived from `SECRET_KEY` (the one secret that lives in `.env`, never in the database). A missing or invalid `SECRET_KEY` fails loudly at boot — there is no silent fallback to storing credentials in plaintext.
- Assumed deployment: trusted LAN. Nothing here is designed to be safely exposed to the public internet without additional hardening (reverse proxy + TLS, rate limiting, etc.) — that's explicitly out of scope for v1.

## What's deliberately NOT in core

- No database beyond SQLite. LifeBoard is a single-household dashboard, not a multi-tenant SaaS; Postgres is not warranted.
- No build step on the frontend. Vanilla JS keeps the bar for "write your own module" at "edit a .py file and maybe a .js file", not "learn our build tooling".
- No module can reach into another module's data or another integration's tables. If two modules want to share derived data, that's a signal to factor the shared logic into a library function both import, not a cross-module read.
