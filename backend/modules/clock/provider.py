"""The clock module is deliberately minimal on the backend: the frontend
renders a live ticking clock locally (see frontend/src/widgets/clock.js,
Phase 2) rather than polling this endpoint every second. get_data() exists
so the module shows up correctly in /api/modules and has a sane fallback
if a custom frontend renderer isn't loaded for some reason.
"""
from datetime import datetime, timezone

from backend.core.base import DashboardModule


class Provider(DashboardModule):
    def get_data(self, db):
        now = datetime.now(timezone.utc).astimezone()
        return {
            "title": "Clock",
            "primary_value": now.strftime("%H:%M"),
            "status": "neutral",
            "lines": [{"label": "Date", "value": now.strftime("%Y-%m-%d")}],
            "updated_at": now.isoformat(),
        }
