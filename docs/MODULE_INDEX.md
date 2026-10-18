# Module Index

A listing of third-party modules/integrations built against LifeBoard's module contract (see [`ARCHITECTURE.md`](ARCHITECTURE.md) and [`MODULE_AUTHORING.md`](MODULE_AUTHORING.md)) — not maintained in anyone's main fork, but documented here so people building their own don't duplicate effort.

## Built-in (ship with this repo)

| Module | Integration | What it shows |
|---|---|---|
| `clock` | *(none)* | Current date/time, live-ticking client-side renderer |
| `training_readiness` | `intervals_icu` | Daily readiness score from HRV, resting HR, sleep, and training load (TSB) |
| `location` | `traccar` | Last known GPS position, reverse-geocoded to a city |
| `weather` | `weather` (wttr.in) | Current temperature/conditions, warns above a configurable wind threshold |
| `nutrition` | *(none — manual entry)* | Logged meals (kcal/protein/carbs/fat) for the day |
| `portfolio` | `portfolio` (NBP + CoinGecko, keyless) | Total crypto+cash value vs cost basis — see [`backend/integrations/portfolio/sync.py`](../backend/integrations/portfolio/sync.py) for why this deliberately excludes stock sources |
| `echo` | `echo` | Smoke-test pair proving the full integration lifecycle works; not meant for daily use, but the best copy-pasteable reference for a new integration+module pair |

## Community modules

None listed yet. If you've built one against this contract and want it listed here (not merged into this repo, just discoverable):

1. Open a PR adding a row to this table: module name, what it needs (API key? self-hosted server? nothing?), and a link to your fork/gist/repo containing the four files.
2. No code review requirement for a listing here — this is a pointer, not an endorsement. Use your judgment before installing someone else's `sync.py`/`provider.py` (they're plain Python files with database access, same trust model as any dependency you'd `pip install`).

## Writing your own

See [`MODULE_AUTHORING.md`](MODULE_AUTHORING.md) for the full walkthrough, or run the scaffolding generator for a head start:

```bash
scripts/new_module.sh my_module --with-integration   # or omit the flag for a display-only module
```
