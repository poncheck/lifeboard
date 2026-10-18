"""The nutrition module: a simple manual-entry card (per
docs/ARCHITECTURE.md's Phase 3 plan). Unlike every other module, this
one has no integration half — there's nothing to sync, meals are
user-entered directly via POST /api/nutrition/entries (see
backend/main.py). This provider just reads today's logged totals back.

Independent of Marcin's existing ~/.hermes/memories/posilki.db (decision
5: LifeBoard syncs/stores its own copy of everything, never reaches
into Hermes's existing databases).
"""
from datetime import date, datetime, timezone

from backend.core.base import DashboardModule


class Provider(DashboardModule):
    def get_data(self, db) -> dict:
        today = date.today().isoformat()
        try:
            row = db.execute(
                "SELECT COALESCE(SUM(kcal), 0), COALESCE(SUM(protein_g), 0), "
                "COALESCE(SUM(carbs_g), 0), COALESCE(SUM(fat_g), 0), COUNT(*) "
                "FROM nutrition_log WHERE day = ?",
                (today,),
            ).fetchone()
        except Exception:
            row = None  # table doesn't exist yet — nothing logged ever

        if row is None or row[4] == 0:
            return {
                "title": "Nutrition",
                "primary_value": "0",
                "primary_unit": "kcal today",
                "status": "neutral",
                "lines": [{"label": "Meals logged", "value": "0"}],
            }

        kcal, protein_g, carbs_g, fat_g, meal_count = row
        return {
            "title": "Nutrition",
            "primary_value": f"{kcal:.0f}",
            "primary_unit": "kcal today",
            "status": "ok",
            "lines": [
                {"label": "Protein", "value": f"{protein_g:.0f}g"},
                {"label": "Carbs", "value": f"{carbs_g:.0f}g"},
                {"label": "Fat", "value": f"{fat_g:.0f}g"},
                {"label": "Meals logged", "value": str(meal_count)},
            ],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
