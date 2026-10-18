"""The training_readiness module: reads the intervals_icu integration's
synced wellness rows and reproduces the scoring logic from the existing
Hermes script (~/.hermes/scripts/training_readiness.py) — same weights
and thresholds, just reading from LifeBoard's own database instead of
calling Intervals.icu directly (per docs/ARCHITECTURE.md's integrations
table).
"""
from datetime import date, datetime, timedelta, timezone

from backend.core.base import DashboardModule

# How many of the most recent days (excluding today/yesterday) to
# average for the HRV/resting-HR baseline. Matches the reference
# script's use of its full 14-day wellness pull minus today/yesterday.
_BASELINE_DAYS = 12


class Provider(DashboardModule):
    def get_data(self, db) -> dict:
        try:
            rows = db.execute(
                "SELECT day, hrv, resting_hr, sleep_score, sleep_secs, ctl, atl "
                "FROM intervals_icu_wellness ORDER BY day DESC LIMIT ?",
                (_BASELINE_DAYS + 2,),
            ).fetchall()
        except Exception:
            rows = []  # table doesn't exist yet — no sync has run

        if not rows:
            return {
                "title": "Training Readiness",
                "primary_value": "no data yet",
                "status": "neutral",
            }

        by_day = {
            r[0]: {
                "hrv": r[1],
                "resting_hr": r[2],
                "sleep_score": r[3],
                "sleep_secs": r[4],
                "ctl": r[5],
                "atl": r[6],
            }
            for r in rows
        }

        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()

        today_data = by_day.get(today) or by_day.get(max(by_day.keys()))
        if today_data is None:
            return {
                "title": "Training Readiness",
                "primary_value": "no data yet",
                "status": "neutral",
            }
        yesterday_data = by_day.get(yesterday)

        baseline_days = [d for d in by_day if d not in (today, yesterday)]
        hrv_values = [by_day[d]["hrv"] for d in baseline_days if by_day[d]["hrv"]]
        hrv_baseline = round(sum(hrv_values) / len(hrv_values), 1) if hrv_values else None
        hr_values = [by_day[d]["resting_hr"] for d in baseline_days if by_day[d]["resting_hr"]]
        hr_baseline = round(sum(hr_values) / len(hr_values), 1) if hr_values else None

        def _value(field):
            val = today_data.get(field)
            if val is None and yesterday_data:
                val = yesterday_data.get(field)
            return val

        hrv_today = _value("hrv")
        hr_today = _value("resting_hr")
        sleep_score = _value("sleep_score")
        sleep_secs = _value("sleep_secs") or 0
        sleep_h = round(sleep_secs / 3600, 1)
        ctl = today_data.get("ctl") or 0
        atl = today_data.get("atl") or 0
        tsb = round(ctl - atl, 1)

        score = 0
        lines = []

        if hrv_today and hrv_baseline:
            hrv_pct = (hrv_today - hrv_baseline) / hrv_baseline * 100
            if hrv_pct >= 5:
                score += 35
            elif hrv_pct >= -5:
                score += 25
            elif hrv_pct >= -15:
                score += 12
            lines.append({"label": "HRV", "value": f"{hrv_today:.0f} ({hrv_pct:+.0f}% vs {hrv_baseline:.0f})"})

        if hr_today and hr_baseline:
            hr_diff = hr_today - hr_baseline
            if hr_diff <= 1:
                score += 20
            elif hr_diff <= 4:
                score += 12
            else:
                score += 4
            lines.append({"label": "Resting HR", "value": f"{hr_today:.0f} bpm ({hr_diff:+.0f} vs baseline)"})

        if sleep_score is not None:
            if sleep_score >= 80 and sleep_h >= 7:
                score += 25
            elif sleep_score >= 65 and sleep_h >= 6:
                score += 17
            elif sleep_score >= 50:
                score += 8
            lines.append({"label": "Sleep", "value": f"{sleep_score:.0f}/100, {sleep_h}h"})

        if tsb >= 10:
            score += 20
        elif tsb >= 0:
            score += 15
        elif tsb >= -10:
            score += 8
        else:
            score += 2
        lines.append({"label": "TSB", "value": f"{tsb:+.1f} (CTL={ctl:.0f}, ATL={atl:.0f})"})

        hard_override = tsb <= -15
        if hard_override:
            status = "alert"
            verdict = "Rest priority (TSB override)"
        elif score >= 80:
            status = "ok"
            verdict = "Green light — go hard"
        elif score >= 60:
            status = "warn"
            verdict = "Yellow — train with care"
        elif score >= 40:
            status = "warn"
            verdict = "Orange — light/active recovery"
        else:
            status = "alert"
            verdict = "Red — rest priority"
        lines.append({"label": "Verdict", "value": verdict})

        return {
            "title": "Training Readiness",
            "primary_value": str(score),
            "primary_unit": "/100",
            "status": status,
            "lines": lines,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
