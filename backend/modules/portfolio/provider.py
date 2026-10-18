"""The portfolio module: reads the portfolio integration's synced
holdings and shows total value + gain/loss vs cost basis. Per
docs/ARCHITECTURE.md's Phase 6 note, this one's inherently personal
(deferred here to crypto+cash only — see backend/integrations/portfolio/sync.py
for why stock sources were left out of the first-class integration).
"""
from datetime import datetime, timezone

from backend.core.base import DashboardModule


class Provider(DashboardModule):
    def get_data(self, db) -> dict:
        try:
            rows = db.execute(
                "SELECT symbol, kind, value_pln, cost_basis_pln FROM portfolio_holdings ORDER BY value_pln DESC"
            ).fetchall()
        except Exception:
            rows = []  # table doesn't exist yet — no sync has run

        if not rows:
            return {
                "title": "Portfolio",
                "primary_value": "no data yet",
                "status": "neutral",
            }

        total_value = sum(r[2] for r in rows)
        total_cost = sum(r[3] for r in rows if r[3] is not None)

        status = "neutral"
        pct_line = None
        if total_cost:
            pct = (total_value - total_cost) / total_cost * 100
            status = "ok" if pct >= 0 else "warn"
            pct_line = f"{pct:+.1f}% vs cost"

        # Top 3 holdings by value as detail lines.
        lines = [{"label": symbol, "value": f"{value:,.0f} PLN"} for symbol, _, value, _ in rows[:3]]
        if pct_line:
            lines.append({"label": "Change", "value": pct_line})

        return {
            "title": "Portfolio",
            "primary_value": f"{total_value:,.0f}",
            "primary_unit": "PLN",
            "status": status,
            "lines": lines,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
