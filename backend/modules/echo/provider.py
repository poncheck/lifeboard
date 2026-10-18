"""Reads back whatever value the echo integration synced. See
backend/integrations/echo/sync.py for the other half.
"""
from backend.core.base import DashboardModule


class Provider(DashboardModule):
    def get_data(self, db):
        try:
            row = db.execute(
                "SELECT value FROM echo_data ORDER BY id DESC LIMIT 1"
            ).fetchone()
        except Exception:
            row = None  # table doesn't exist yet — no sync has run

        if row is None:
            return {
                "title": "Echo",
                "primary_value": "no data yet",
                "status": "neutral",
            }
        return {"title": "Echo", "primary_value": row[0], "status": "ok"}
