"""The intervals_icu integration: pulls daily wellness rows (HRV,
resting HR, sleep score/duration, CTL/ATL) from the Intervals.icu REST
API and writes normalized rows into LifeBoard's own database. Reference
implementation for the scoring logic: ~/.hermes/scripts/training_readiness.py
(per docs/ARCHITECTURE.md's integrations table — LifeBoard calls the
platform API itself rather than reading Marcin's existing script output).

Auth: HTTP Basic with username "API_KEY" and the user's API key as the
password — this is Intervals.icu's documented API auth scheme, not a
LifeBoard convention.
"""
import base64
import json
import urllib.request
from datetime import date, timedelta

from backend.core.base import Integration

_API_BASE = "https://intervals.icu/api/v1"
# How many days of wellness history to pull each sync — enough to
# compute a HRV/resting-HR baseline (training_readiness.py's reference
# implementation uses 14) plus a cushion for sync gaps.
_LOOKBACK_DAYS = 21


def _auth_header(api_key: str) -> str:
    token = base64.b64encode(f"API_KEY:{api_key}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _athlete_path(athlete_id: str) -> str:
    return athlete_id.strip() if athlete_id and athlete_id.strip() else "0"


def _fetch_wellness(athlete_id: str, api_key: str, oldest: str, newest: str) -> list[dict]:
    url = (
        f"{_API_BASE}/athlete/{_athlete_path(athlete_id)}/wellness.json"
        f"?oldest={oldest}&newest={newest}"
    )
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": _auth_header(api_key),
            "Accept": "application/json",
            # Intervals.icu sits behind Cloudflare, which blocks
            # Python's default "Python-urllib/x.y" User-Agent outright
            # (403 "browser_signature_banned") — a normal-looking UA
            # string is required, not optional, for every request.
            "User-Agent": "LifeBoard/1.0 (+https://github.com/poncheck/lifeboard)",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read())


class Sync(Integration):
    def test_connection(self, credentials: dict) -> bool:
        api_key = credentials.get("api_key")
        athlete_id = credentials.get("athlete_id", "0")
        if not api_key:
            return False
        try:
            today = date.today().isoformat()
            # Cheap, read-only: ask for a single day's wellness. A valid
            # key + athlete returns 200 with a (possibly empty) list; a
            # bad key returns 401/403; a bad athlete ID returns 404 —
            # all are "connection test failed", not an exception that
            # escapes this method.
            _fetch_wellness(athlete_id, api_key, today, today)
            return True
        except Exception:
            return False

    def sync(self, credentials: dict, db) -> None:
        api_key = credentials.get("api_key")
        athlete_id = credentials.get("athlete_id", "0")
        if not api_key:
            return

        oldest = (date.today() - timedelta(days=_LOOKBACK_DAYS)).isoformat()
        newest = date.today().isoformat()

        # Raising here (bad credentials, network error, platform outage)
        # is intentional: integration_registry.sync() catches it, logs
        # it, and reports (success=False, error) for the admin panel's
        # status line. See backend/core/base.py.
        rows = _fetch_wellness(athlete_id, api_key, oldest, newest)

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS intervals_icu_wellness (
                day TEXT PRIMARY KEY,
                hrv REAL,
                resting_hr REAL,
                sleep_score REAL,
                sleep_secs REAL,
                ctl REAL,
                atl REAL
            )
            """
        )
        for row in rows:
            day = row.get("id")
            if not day:
                continue
            db.execute(
                """
                INSERT INTO intervals_icu_wellness
                    (day, hrv, resting_hr, sleep_score, sleep_secs, ctl, atl)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(day) DO UPDATE SET
                    hrv = excluded.hrv,
                    resting_hr = excluded.resting_hr,
                    sleep_score = excluded.sleep_score,
                    sleep_secs = excluded.sleep_secs,
                    ctl = excluded.ctl,
                    atl = excluded.atl
                """,
                (
                    day,
                    row.get("hrv"),
                    row.get("restingHR"),
                    row.get("sleepScore"),
                    row.get("sleepSecs"),
                    row.get("ctl"),
                    row.get("atl"),
                ),
            )
        db.commit()
