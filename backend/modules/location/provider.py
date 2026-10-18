"""The location module: reads the traccar integration's last synced
position and shows a reverse-geocoded city, degrading gracefully (per
docs/ARCHITECTURE.md's Phase 3 plan) when Traccar hasn't synced yet.
"""
from datetime import datetime, timezone

from backend.core.base import DashboardModule


class Provider(DashboardModule):
    def get_data(self, db) -> dict:
        try:
            row = db.execute(
                "SELECT latitude, longitude, fix_time, city, country "
                "FROM traccar_last_position ORDER BY device_id LIMIT 1"
            ).fetchone()
        except Exception:
            row = None  # table doesn't exist yet — no sync has run

        if row is None:
            return {
                "title": "Location",
                "primary_value": "not connected",
                "status": "neutral",
            }

        lat, lon, fix_time, city, country = row
        primary = city or f"{lat:.3f}, {lon:.3f}"

        lines = [{"label": "Coordinates", "value": f"{lat:.4f}, {lon:.4f}"}]
        if country:
            lines.append({"label": "Country", "value": country})

        return {
            "title": "Location",
            "primary_value": primary,
            "status": "ok",
            "lines": lines,
            "updated_at": fix_time or datetime.now(timezone.utc).isoformat(),
        }
