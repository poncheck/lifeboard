"""Tests for the built-in traccar integration + location module.
Network calls (both Traccar's /api/positions and Nominatim reverse
geocoding) are mocked — no real Traccar server needed.
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


_POSITIONS = [
    {
        "deviceId": 1,
        "latitude": 50.8991,
        "longitude": 15.7726,
        "fixTime": "2026-10-18T09:00:00.000+00:00",
    }
]
_GEOCODE = {"address": {"city": "Jelenia Góra", "country": "Poland"}, "display_name": "Jelenia Góra, Poland"}


def _mock_urlopen_sequence(*payloads):
    """Returns a side_effect function so successive urlopen() calls
    (positions, then geocode) return different canned responses."""
    iterator = iter(payloads)

    def _side_effect(*args, **kwargs):
        response = _response(next(iterator))
        mock_cm = type("MockCM", (), {"__enter__": lambda self: response, "__exit__": lambda self, *a: None})()
        return mock_cm

    return _side_effect


def test_traccar_test_connection_true_on_200(db):
    from backend.integrations.traccar.sync import Sync

    with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(_POSITIONS)):
        sync = Sync()
        assert sync.test_connection({"server_url": "https://traccar.example.com", "api_token": "tok"}) is True


def test_traccar_test_connection_false_without_credentials(db):
    from backend.integrations.traccar.sync import Sync

    sync = Sync()
    assert sync.test_connection({"server_url": "", "api_token": ""}) is False


def test_traccar_sync_writes_position_and_geocodes(db):
    from backend.integrations.traccar.sync import Sync

    with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(_POSITIONS, _GEOCODE)):
        Sync().sync({"server_url": "https://traccar.example.com", "api_token": "tok", "device_id": "1"}, db)

    row = db.execute(
        "SELECT device_id, latitude, longitude, city, country FROM traccar_last_position WHERE device_id = 1"
    ).fetchone()
    assert row == (1, 50.8991, 15.7726, "Jelenia Góra", "Poland")


def test_traccar_sync_is_idempotent_upserts_not_duplicates(db):
    from backend.integrations.traccar.sync import Sync

    with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(_POSITIONS, _GEOCODE)):
        Sync().sync({"server_url": "https://traccar.example.com", "api_token": "tok", "device_id": "1"}, db)

    moved = [{**_POSITIONS[0], "latitude": 51.0, "longitude": 16.0}]
    with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(moved, _GEOCODE)):
        Sync().sync({"server_url": "https://traccar.example.com", "api_token": "tok", "device_id": "1"}, db)

    count = db.execute("SELECT COUNT(*) FROM traccar_last_position").fetchone()[0]
    assert count == 1
    lat = db.execute("SELECT latitude FROM traccar_last_position WHERE device_id = 1").fetchone()[0]
    assert lat == 51.0


def test_traccar_sync_raises_on_network_error(db):
    from backend.integrations.traccar.sync import Sync

    with patch("urllib.request.urlopen", side_effect=OSError("network down")):
        with pytest.raises(OSError):
            Sync().sync({"server_url": "https://traccar.example.com", "api_token": "tok"}, db)


def test_location_provider_not_connected_before_any_sync(db):
    from backend.modules.location.provider import Provider

    result = Provider().get_data(db)
    assert result["primary_value"] == "not connected"
    assert result["status"] == "neutral"


def test_location_provider_shows_city_after_sync(db):
    from backend.integrations.traccar.sync import Sync
    from backend.modules.location.provider import Provider

    with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(_POSITIONS, _GEOCODE)):
        Sync().sync({"server_url": "https://traccar.example.com", "api_token": "tok", "device_id": "1"}, db)

    result = Provider().get_data(db)
    assert result["primary_value"] == "Jelenia Góra"
    assert result["status"] == "ok"
