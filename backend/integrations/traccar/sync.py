"""The traccar integration: pulls the latest GPS position from a
Traccar server's /api/positions endpoint and writes it into LifeBoard's
own database. Reverse geocoding (Nominatim) is done here too so the
location module never makes a network call (see docs/ARCHITECTURE.md:
"a module never talks to a third-party API directly").

Auth: Bearer token in the Authorization header. Traccar also supports
session-cookie login (used by some older scripts in this household's
Hermes setup), but the API token the user generates in their Traccar
account settings works with Bearer auth directly — no login step
needed, which fits LifeBoard's "paste a credential, test it, done"
admin panel flow better than a stateful session.
"""
import json
import urllib.request

from backend.core.base import Integration

_GEOCODE_URL = "https://nominatim.openstreetmap.org/reverse"


def _fetch_positions(server_url: str, api_token: str) -> list[dict]:
    url = f"{server_url.rstrip('/')}/api/positions"
    request = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {api_token}", "Accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read())


def _reverse_geocode(lat: float, lon: float) -> tuple[str | None, str | None]:
    url = f"{_GEOCODE_URL}?lat={lat}&lon={lon}&format=json&zoom=10"
    request = urllib.request.Request(url, headers={"User-Agent": "LifeBoard/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read())
        address = data.get("address", {})
        city = (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("municipality")
        )
        country = address.get("country")
        return city, country
    except Exception:
        # Geocoding is a nice-to-have, not critical to the sync itself —
        # a position with no city name is still useful data.
        return None, None


def _find_device(positions: list[dict], device_id: str) -> dict | None:
    if not device_id:
        return positions[0] if positions else None
    try:
        target = int(device_id)
    except ValueError:
        return positions[0] if positions else None
    for position in positions:
        if position.get("deviceId") == target:
            return position
    return None


class Sync(Integration):
    def test_connection(self, credentials: dict) -> bool:
        server_url = credentials.get("server_url")
        api_token = credentials.get("api_token")
        if not server_url or not api_token:
            return False
        try:
            _fetch_positions(server_url, api_token)
            return True
        except Exception:
            return False

    def sync(self, credentials: dict, db) -> None:
        server_url = credentials.get("server_url")
        api_token = credentials.get("api_token")
        device_id = credentials.get("device_id", "")
        if not server_url or not api_token:
            return

        # Raising on failure is intentional — see backend/core/base.py's
        # updated Integration.sync() contract.
        positions = _fetch_positions(server_url, api_token)
        position = _find_device(positions, device_id)

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS traccar_last_position (
                device_id INTEGER PRIMARY KEY,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                fix_time TEXT NOT NULL,
                city TEXT,
                country TEXT
            )
            """
        )
        if position is None:
            return

        lat, lon = position["latitude"], position["longitude"]
        city, country = _reverse_geocode(lat, lon)
        db.execute(
            """
            INSERT INTO traccar_last_position
                (device_id, latitude, longitude, fix_time, city, country)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                fix_time = excluded.fix_time,
                city = excluded.city,
                country = excluded.country
            """,
            (position.get("deviceId", 0), lat, lon, position.get("fixTime", ""), city, country),
        )
        db.commit()
