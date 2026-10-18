"""The weather integration: pulls current conditions for a city from
wttr.in — a keyless JSON endpoint, no API key/registration required
(per docs/ARCHITECTURE.md's integrations table — "decision confirmed,
matches Marcin's existing script pattern"). Writes a single normalized
row into LifeBoard's own database for the weather module to read.
"""
import json
import urllib.parse
import urllib.request

from backend.core.base import Integration

_WTTR_BASE = "https://wttr.in"


def _fetch_current_conditions(city: str) -> dict:
    encoded_city = urllib.parse.quote(city)
    url = f"{_WTTR_BASE}/{encoded_city}?format=j1"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.loads(response.read())
    return data["current_condition"][0]


class Sync(Integration):
    def test_connection(self, credentials: dict) -> bool:
        city = credentials.get("city")
        if not city:
            return False
        try:
            _fetch_current_conditions(city)
            return True
        except Exception:
            return False

    def sync(self, credentials: dict, db) -> None:
        city = credentials.get("city")
        if not city:
            return

        high_wind_kmh = credentials.get("high_wind_kmh")
        try:
            high_wind_kmh = float(high_wind_kmh) if high_wind_kmh else 40.0
        except (TypeError, ValueError):
            high_wind_kmh = 40.0

        # Raising on failure is intentional — see backend/core/base.py's
        # updated Integration.sync() contract.
        condition = _fetch_current_conditions(city)

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS weather_current (
                city TEXT PRIMARY KEY,
                temp_c REAL,
                feels_like_c REAL,
                wind_kmh REAL,
                humidity REAL,
                description TEXT,
                observed_at TEXT,
                high_wind_threshold_kmh REAL
            )
            """
        )
        db.execute(
            """
            INSERT INTO weather_current
                (city, temp_c, feels_like_c, wind_kmh, humidity, description, observed_at, high_wind_threshold_kmh)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(city) DO UPDATE SET
                temp_c = excluded.temp_c,
                feels_like_c = excluded.feels_like_c,
                wind_kmh = excluded.wind_kmh,
                humidity = excluded.humidity,
                description = excluded.description,
                observed_at = excluded.observed_at,
                high_wind_threshold_kmh = excluded.high_wind_threshold_kmh
            """,
            (
                city,
                float(condition.get("temp_C", 0)),
                float(condition.get("FeelsLikeC", 0)),
                float(condition.get("windspeedKmph", 0)),
                float(condition.get("humidity", 0)),
                (condition.get("weatherDesc") or [{}])[0].get("value", ""),
                condition.get("observation_time", ""),
                high_wind_kmh,
            ),
        )
        db.commit()
