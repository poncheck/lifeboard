# LifeBoard

> Your life, at a glance.

A self-hosted, Docker-deployed personal dashboard for your local network. Clock, training readiness, nutrition, location, weather — one screen, one glance.

Built on an **open, pluggable integration/module system**: anyone can write a new integration (connects to a platform's API, syncs data into LifeBoard's own database) or a dashboard module (displays that data as a card) without touching the core. Fork it, point it at your own accounts, done.

![LifeBoard screenshot placeholder](docs/screenshot-placeholder.png)

## Why

Most personal dashboards either lock you into someone else's cloud service, or require you to hand-wire every widget yourself. LifeBoard is the middle ground: self-hosted (your data never leaves your network), but with a real plugin contract so adding "my own weather station" or "my own habit tracker" is a matter of dropping a folder in, not forking the whole app.

## Status

🚧 Early development. See [the implementation plan](docs/ARCHITECTURE.md) for the roadmap. Phase 0 (this commit) is scaffolding only — no running functionality yet.

## Quick start (once Phase 1 lands)

```bash
git clone https://github.com/poncheck/lifeboard.git
cd lifeboard
cp .env.example .env
# edit .env: set SECRET_KEY to a random 32+ char string
docker compose up
```

Open `http://<this-machine's-ip>:8420` in a browser on your LAN. First boot walks you through a short setup wizard (name, date of birth, email, admin password), then you're in. Add integrations (Intervals.icu, Traccar, ...) from the admin panel — each one syncs on its own schedule into LifeBoard's own database. Enable the dashboard modules that go with the integrations you've configured.

Works on a laptop browser as the primary surface; "Add to Home Screen" on a phone for an app-like shortcut.

## Writing your own module

See [`docs/MODULE_AUTHORING.md`](docs/MODULE_AUTHORING.md) (coming in Phase 1) for the full guide. Short version: a module is a folder with a `module.json` manifest and a `provider.py` returning a small JSON schema; LifeBoard auto-discovers it and renders a card with zero frontend code required. An integration (if your module needs to pull from a third-party API) follows the same pattern with `integration.json` + `sync.py`.

## License

MIT — see [LICENSE](LICENSE).
