"""The weather module: reads the weather integration's synced current
conditions and flags status as "warn" when wind speed exceeds the
configurable high-wind threshold (per docs/ARCHITECTURE.md's Phase 3
plan: "status reflecting a configurable high-wind threshold").
"""
from datetime import datetime, timezone

from backend.core.base import DashboardModule


class Provider(DashboardModule):
    def get_data(self, db) -> dict:
        try:
            row = db.execute(
                "SELECT city, temp_c, feels_like_c, wind_kmh, humidity, description, "
                "observed_at, high_wind_threshold_kmh FROM weather_current LIMIT 1"
            ).fetchone()
        except Exception:
            row = None  # table doesn't exist yet — no sync has run

        if row is None:
            return {
                "title": "Weather",
                "primary_value": "no data yet",
                "status": "neutral",
            }

        city, temp_c, feels_like_c, wind_kmh, humidity, description, observed_at, threshold = row
        threshold = threshold or 40.0
        status = "warn" if wind_kmh is not None and wind_kmh >= threshold else "ok"

        return {
            "title": f"Weather — {city}",
            "primary_value": f"{temp_c:.0f}",
            "primary_unit": "°C",
            "status": status,
            "lines": [
                {"label": "Feels like", "value": f"{feels_like_c:.0f}°C"},
                {"label": "Conditions", "value": description or "—"},
                {"label": "Wind", "value": f"{wind_kmh:.0f} km/h"},
                {"label": "Humidity", "value": f"{humidity:.0f}%"},
            ],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
