"""Tests for the built-in intervals_icu integration + training_readiness
module. Network calls are mocked (urllib.request.urlopen patched) — no
real Intervals.icu account needed to verify the sync -> store -> read
pipeline and the readiness scoring logic.
"""
import json
import sqlite3
from datetime import date, timedelta
from io import BytesIO
from unittest.mock import patch

import pytest


def _fake_wellness_response(rows: list[dict]):
    return BytesIO(json.dumps(rows).encode("utf-8"))


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


def test_intervals_icu_test_connection_true_on_200(db):
    from backend.integrations.intervals_icu.sync import Sync

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = _fake_wellness_response([])
        sync = Sync()
        assert sync.test_connection({"api_key": "valid-key", "athlete_id": "0"}) is True


def test_intervals_icu_test_connection_false_without_api_key(db):
    from backend.integrations.intervals_icu.sync import Sync

    sync = Sync()
    assert sync.test_connection({"api_key": "", "athlete_id": "0"}) is False


def test_intervals_icu_test_connection_false_on_network_error(db):
    from backend.integrations.intervals_icu.sync import Sync

    with patch("urllib.request.urlopen", side_effect=OSError("network down")):
        sync = Sync()
        assert sync.test_connection({"api_key": "key", "athlete_id": "0"}) is False


def test_intervals_icu_sync_writes_wellness_rows(db):
    from backend.integrations.intervals_icu.sync import Sync

    today = date.today().isoformat()
    fake_rows = [
        {"id": today, "hrv": 85.0, "restingHR": 45, "sleepScore": 80, "sleepSecs": 27000, "ctl": 80, "atl": 70},
    ]
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = _fake_wellness_response(fake_rows)
        Sync().sync({"api_key": "key", "athlete_id": "0"}, db)

    row = db.execute(
        "SELECT day, hrv, resting_hr, sleep_score, ctl, atl FROM intervals_icu_wellness WHERE day = ?",
        (today,),
    ).fetchone()
    assert row == (today, 85.0, 45, 80, 80, 70)


def test_intervals_icu_sync_is_idempotent_upserts_not_duplicates(db):
    from backend.integrations.intervals_icu.sync import Sync

    today = date.today().isoformat()
    fake_rows = [{"id": today, "hrv": 85.0, "restingHR": 45, "sleepScore": 80, "sleepSecs": 27000, "ctl": 80, "atl": 70}]

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = _fake_wellness_response(fake_rows)
        Sync().sync({"api_key": "key", "athlete_id": "0"}, db)

    fake_rows_updated = [{"id": today, "hrv": 90.0, "restingHR": 44, "sleepScore": 85, "sleepSecs": 28000, "ctl": 82, "atl": 68}]
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = _fake_wellness_response(fake_rows_updated)
        Sync().sync({"api_key": "key", "athlete_id": "0"}, db)

    count = db.execute("SELECT COUNT(*) FROM intervals_icu_wellness WHERE day = ?", (today,)).fetchone()[0]
    assert count == 1
    hrv = db.execute("SELECT hrv FROM intervals_icu_wellness WHERE day = ?", (today,)).fetchone()[0]
    assert hrv == 90.0


def test_intervals_icu_sync_raises_on_network_error_does_not_write(db):
    from backend.integrations.intervals_icu.sync import Sync

    with patch("urllib.request.urlopen", side_effect=OSError("network down")):
        with pytest.raises(OSError):
            Sync().sync({"api_key": "key", "athlete_id": "0"}, db)


def test_training_readiness_provider_no_data_before_any_sync(db):
    from backend.modules.training_readiness.provider import Provider

    result = Provider().get_data(db)
    assert result["primary_value"] == "no data yet"
    assert result["status"] == "neutral"


def test_training_readiness_provider_scores_good_hrv_and_tsb_as_ok(db):
    from backend.integrations.intervals_icu.sync import Sync
    from backend.modules.training_readiness.provider import Provider

    today = date.today()
    rows = []
    # 12 baseline days with hrv=80, resting_hr=45
    for i in range(2, 14):
        day = (today - timedelta(days=i)).isoformat()
        rows.append({"id": day, "hrv": 80.0, "restingHR": 45, "sleepScore": 75, "sleepSecs": 25200, "ctl": 70, "atl": 60})
    # Today: hrv well above baseline, great sleep, positive TSB
    rows.append(
        {"id": today.isoformat(), "hrv": 90.0, "restingHR": 44, "sleepScore": 85, "sleepSecs": 27000, "ctl": 80, "atl": 60}
    )

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = _fake_wellness_response(rows)
        Sync().sync({"api_key": "key", "athlete_id": "0"}, db)

    result = Provider().get_data(db)
    assert result["status"] == "ok"
    assert int(result["primary_value"]) >= 80


def test_training_readiness_provider_hard_overrides_to_alert_on_very_low_tsb(db):
    from backend.integrations.intervals_icu.sync import Sync
    from backend.modules.training_readiness.provider import Provider

    today = date.today()
    rows = []
    for i in range(2, 14):
        day = (today - timedelta(days=i)).isoformat()
        rows.append({"id": day, "hrv": 80.0, "restingHR": 45, "sleepScore": 75, "sleepSecs": 25200, "ctl": 70, "atl": 60})
    # Today: great HRV/sleep but TSB <= -15 must still override to alert
    rows.append(
        {"id": today.isoformat(), "hrv": 95.0, "restingHR": 43, "sleepScore": 90, "sleepSecs": 28800, "ctl": 70, "atl": 90}
    )

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = _fake_wellness_response(rows)
        Sync().sync({"api_key": "key", "athlete_id": "0"}, db)

    result = Provider().get_data(db)
    assert result["status"] == "alert"
