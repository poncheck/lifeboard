"""Tests for the built-in weather integration (wttr.in) + weather
module. Network calls are mocked — no real network access needed.
"""
import json
import sqlite3
from io import BytesIO
from unittest.mock import patch

import pytest


def _response(payload):
    return BytesIO(json.dumps(payload).encode("utf-8"))


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


def _mock_urlopen(payload):
    response = _response(payload)
    mock_cm = type("MockCM", (), {"__enter__": lambda self: response, "__exit__": lambda self, *a: None})()
    return mock_cm


_CALM_CONDITIONS = {
    "current_condition": [
        {
            "temp_C": "10",
            "FeelsLikeC": "8",
            "windspeedKmph": "12",
            "humidity": "80",
            "weatherDesc": [{"value": "Partly cloudy"}],
            "observation_time": "09:00 AM",
        }
    ]
}

_WINDY_CONDITIONS = {
    "current_condition": [
        {
            "temp_C": "15",
            "FeelsLikeC": "13",
            "windspeedKmph": "55",
            "humidity": "60",
            "weatherDesc": [{"value": "Windy"}],
            "observation_time": "09:00 AM",
        }
    ]
}


def test_weather_test_connection_true_on_200(db):
    from backend.integrations.weather.sync import Sync

    with patch("urllib.request.urlopen", return_value=_mock_urlopen(_CALM_CONDITIONS)):
        assert Sync().test_connection({"city": "Jelenia Gora"}) is True


def test_weather_test_connection_false_without_city(db):
    from backend.integrations.weather.sync import Sync

    assert Sync().test_connection({"city": ""}) is False


def test_weather_sync_writes_current_conditions(db):
    from backend.integrations.weather.sync import Sync

    with patch("urllib.request.urlopen", return_value=_mock_urlopen(_CALM_CONDITIONS)):
        Sync().sync({"city": "Jelenia Gora"}, db)

    row = db.execute(
        "SELECT city, temp_c, feels_like_c, wind_kmh, description FROM weather_current WHERE city = ?",
        ("Jelenia Gora",),
    ).fetchone()
    assert row == ("Jelenia Gora", 10.0, 8.0, 12.0, "Partly cloudy")


def test_weather_sync_is_idempotent_upserts_not_duplicates(db):
    from backend.integrations.weather.sync import Sync

    with patch("urllib.request.urlopen", return_value=_mock_urlopen(_CALM_CONDITIONS)):
        Sync().sync({"city": "Jelenia Gora"}, db)
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(_WINDY_CONDITIONS)):
        Sync().sync({"city": "Jelenia Gora"}, db)

    count = db.execute("SELECT COUNT(*) FROM weather_current WHERE city = ?", ("Jelenia Gora",)).fetchone()[0]
    assert count == 1
    wind = db.execute("SELECT wind_kmh FROM weather_current WHERE city = ?", ("Jelenia Gora",)).fetchone()[0]
    assert wind == 55.0


def test_weather_sync_raises_on_network_error(db):
    from backend.integrations.weather.sync import Sync

    with patch("urllib.request.urlopen", side_effect=OSError("network down")):
        with pytest.raises(OSError):
            Sync().sync({"city": "Jelenia Gora"}, db)


def test_weather_provider_no_data_before_any_sync(db):
    from backend.modules.weather.provider import Provider

    result = Provider().get_data(db)
    assert result["primary_value"] == "no data yet"
    assert result["status"] == "neutral"


def test_weather_provider_status_ok_under_wind_threshold(db):
    from backend.integrations.weather.sync import Sync
    from backend.modules.weather.provider import Provider

    with patch("urllib.request.urlopen", return_value=_mock_urlopen(_CALM_CONDITIONS)):
        Sync().sync({"city": "Jelenia Gora", "high_wind_kmh": "40"}, db)

    result = Provider().get_data(db)
    assert result["status"] == "ok"
    assert result["primary_value"] == "10"


def test_weather_provider_status_warn_over_configured_wind_threshold(db):
    from backend.integrations.weather.sync import Sync
    from backend.modules.weather.provider import Provider

    with patch("urllib.request.urlopen", return_value=_mock_urlopen(_WINDY_CONDITIONS)):
        Sync().sync({"city": "Jelenia Gora", "high_wind_kmh": "40"}, db)

    result = Provider().get_data(db)
    assert result["status"] == "warn"
