# LifeBoard

> Your life, at a glance.

A self-hosted, Docker-deployed personal dashboard for your local network. Clock, training readiness, nutrition, location, weather — one screen, one glance.

Built on an **open, pluggable integration/module system**: anyone can write a new integration (connects to a platform's API, syncs data into LifeBoard's own database) or a dashboard module (displays that data as a card) without touching the core. Fork it, point it at your own accounts, done.

## Why

Most personal dashboards either lock you into someone else's cloud service, or require you to hand-wire every widget yourself. LifeBoard is the middle ground: self-hosted (your data never leaves your network), but with a real plugin contract so adding "my own weather station" or "my own habit tracker" is a matter of dropping a folder in, not forking the whole app.

## Status

✅ Phases 0–5 complete: auth, the full integration/module registry + scheduler, a responsive no-build-step frontend, four real integrations (Intervals.icu, Traccar, wttr.in weather, manual nutrition logging) with their matching dashboard modules, drag-to-reposition + per-module refresh + dark/light theme, and account settings (change password, log out all sessions). 86+ backend tests, all passing; the full stack has been exercised against real third-party accounts, not just mocks. See [`ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design and [`MODULE_AUTHORING.md`](docs/MODULE_AUTHORING.md) to write your own module.

Phase 6 (stretch goals — a Marcin-specific `portfolio` module, multi-user accounts, a module scaffolding generator) is optional future work, not required for daily use.

## Quick start

```bash
git clone https://github.com/poncheck/lifeboard.git
cd lifeboard
cp .env.example .env
# edit .env: set SECRET_KEY to a random 32+ char string
#   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
docker compose up
```

Open `http://<this-machine's-ip>:8420` in a browser on your LAN. First boot walks you through a short setup wizard (name, date of birth, email, admin password), then you're in. Add integrations (Intervals.icu, Traccar, a city for weather, ...) from the admin panel (**Integrations** in the top nav) — each one syncs on its own schedule into LifeBoard's own database; "Sync now" triggers an immediate sync without waiting. Enable the dashboard modules that go with the integrations you've configured from **Configure** on the dashboard.

Works on a laptop browser as the primary surface; "Add to Home Screen" on a phone for an app-like shortcut (standalone display, no browser chrome).

## Built-in integrations + modules

| Integration | Credentials needed | Feeds module |
|---|---|---|
| Intervals.icu | API key (from your Intervals.icu account settings) | Training Readiness — HRV/sleep/TSB-based readiness score |
| Traccar | Server URL + API token | Location — last known position, reverse-geocoded to a city |
| Weather (wttr.in) | Just a city name — no API key | Weather — current temp/conditions, warns above a configurable wind threshold |
| *(none)* | — | Nutrition — manual meal logging (kcal/protein/carbs/fat), no third-party account needed |
| *(none)* | — | Clock — built-in, always available |

## Writing your own module

See [`docs/MODULE_AUTHORING.md`](docs/MODULE_AUTHORING.md) for the full walkthrough: the two-halves contract, two copy-pasteable examples (a display-only module, and the full `echo` integration+module pair), the generic card schema, local testing, and the PR checklist for contributing a module back. Short version: a module is a folder with a `module.json` manifest and a `provider.py` returning a small JSON schema; LifeBoard auto-discovers it and renders a card with zero frontend code required. An integration (if your module needs to pull from a third-party API) follows the same pattern with `integration.json` + `sync.py`.

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design: the integration/module split and why, the API surface, the frontend widget contract, and the security model.

## License

MIT — see [LICENSE](LICENSE).
