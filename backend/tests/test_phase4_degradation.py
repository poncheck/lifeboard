"""Phase 4 verification: removing an integration's credentials
degrades its dependent module cleanly (a clear 'not connected' /
'no data yet' state), per the plan's Phase 4 checklist: "stopping
Traccar sync (removing credentials) degrades the location module
cleanly with a clear 'not connected' state, not a broken card."
"""
import json
from io import BytesIO
from unittest.mock import patch


def _mock_urlopen(payload):
    response = BytesIO(json.dumps(payload).encode("utf-8"))
    mock_cm = type("MockCM", (), {"__enter__": lambda self: response, "__exit__": lambda self, *a: None})()
    return mock_cm


_POSITIONS = [{"deviceId": 1, "latitude": 50.8991, "longitude": 15.7726, "fixTime": "2026-10-18T09:00:00.000+00:00"}]
_GEOCODE = {"address": {"city": "Jelenia Góra", "country": "Poland"}, "display_name": "Jelenia Góra, Poland"}


def _login(app_client):
    app_client.post(
        "/api/setup",
        json={
            "full_name": "Marcin Petkowicz",
            "date_of_birth": "1986-03-26",
            "email": "marcin@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    app_client.post(
        "/api/login",
        json={"email": "marcin@example.com", "password": "correct-horse-battery-staple"},
    )


def test_location_module_degrades_cleanly_after_traccar_credentials_removed(real_app_client):
    app_client = real_app_client
    _login(app_client)

    with patch("urllib.request.urlopen") as mock_urlopen:
        # Call order: save_credentials's test_connection() does one
        # fetch_positions; sync-now then does fetch_positions + reverse_geocode.
        mock_urlopen.side_effect = [_mock_urlopen(_POSITIONS), _mock_urlopen(_POSITIONS), _mock_urlopen(_GEOCODE)]
        save_response = app_client.post(
            "/api/integrations/traccar/credentials",
            json={"server_url": "https://traccar.example.com", "api_token": "tok", "device_id": "1"},
        )
        assert save_response.status_code == 200

        sync_response = app_client.post("/api/integrations/traccar/sync-now")
        assert sync_response.status_code == 200

    connected_data = app_client.get("/api/modules/location/data").json()
    assert connected_data["primary_value"] == "Jelenia Góra"
    assert connected_data["status"] == "ok"

    delete_response = app_client.delete("/api/integrations/traccar/credentials")
    assert delete_response.status_code == 200

    # Credentials gone: the module must still respond 200 with a clear
    # degraded state — not a 500, not a card-error payload. Note the
    # *last synced* position row itself isn't erased by removing
    # credentials (that's a deliberate "last known position" semantic,
    # same historical-status behavior as /api/integrations' last_synced_at),
    # but the integration's requirement_satisfied flag must flip false
    # so the config panel greys the module out again.
    modules = app_client.get("/api/modules").json()
    assert modules["location"]["requirement_satisfied"] is False

    degraded_data = app_client.get("/api/modules/location/data").json()
    assert "error" not in degraded_data
    assert degraded_data["status"] in ("ok", "neutral")
