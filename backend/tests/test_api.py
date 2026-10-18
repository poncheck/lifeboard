"""End-to-end API tests for backend.main — the full setup -> login ->
integrations -> modules -> dashboard flow against a real (temp) app.db
and temp module/integration directories. Per docs/ARCHITECTURE.md's
Phase 1 verification checklist.
"""
import json
import textwrap

import pytest
from fastapi.testclient import TestClient


ECHO_MODULE_MANIFEST = {
    "id": "echo",
    "name": "Echo",
    "description": "Test module",
    "icon": "echo",
    "category": "system",
    "default_refresh_seconds": 30,
    "grid_size": "1x1",
    "requires_integration": "echo",
}

ECHO_MODULE_PROVIDER = """
from backend.core.base import DashboardModule

class Provider(DashboardModule):
    def get_data(self, db):
        row = db.execute("SELECT value FROM echo_data ORDER BY id DESC LIMIT 1").fetchone()
        value = row[0] if row else None
        return {"title": "Echo", "primary_value": value or "no data", "status": "ok"}
"""

ECHO_INTEGRATION_MANIFEST = {
    "id": "echo",
    "name": "Echo",
    "description": "Test integration",
    "credential_fields": [{"key": "value", "label": "Value to echo", "secret": False}],
    "sync_interval_seconds": 900,
}

ECHO_INTEGRATION_SYNC = """
from backend.core.base import Integration

class Sync(Integration):
    def test_connection(self, credentials):
        return bool(credentials.get("value"))

    def sync(self, credentials, db):
        db.execute("CREATE TABLE IF NOT EXISTS echo_data (id INTEGER PRIMARY KEY, value TEXT)")
        db.execute("INSERT INTO echo_data (value) VALUES (?)", (credentials.get("value"),))
        db.commit()
"""


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    modules_dir = tmp_path / "modules"
    integrations_dir = tmp_path / "integrations"
    modules_dir.mkdir()
    integrations_dir.mkdir()

    echo_mod_dir = modules_dir / "echo"
    echo_mod_dir.mkdir()
    (echo_mod_dir / "module.json").write_text(json.dumps(ECHO_MODULE_MANIFEST))
    (echo_mod_dir / "provider.py").write_text(textwrap.dedent(ECHO_MODULE_PROVIDER))

    echo_int_dir = integrations_dir / "echo"
    echo_int_dir.mkdir()
    (echo_int_dir / "integration.json").write_text(json.dumps(ECHO_INTEGRATION_MANIFEST))
    (echo_int_dir / "sync.py").write_text(textwrap.dedent(ECHO_INTEGRATION_SYNC))

    monkeypatch.setenv("LIFEBOARD_SECRET_KEY", "test-secret-key-long-enough-for-tests")
    monkeypatch.setenv("LIFEBOARD_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LIFEBOARD_MODULES_DIR", str(modules_dir))
    monkeypatch.setenv("LIFEBOARD_INTEGRATIONS_DIR", str(integrations_dir))
    monkeypatch.setenv("LIFEBOARD_LAYOUT_PATH", str(tmp_path / "dashboard.yaml"))

    from backend.main import create_app

    app = create_app()
    return TestClient(app)


def test_healthz_requires_no_auth(app_client):
    response = app_client.get("/healthz")
    assert response.status_code == 200


def test_protected_route_without_session_returns_401(app_client):
    response = app_client.get("/api/modules")
    assert response.status_code == 401


def test_setup_then_login_then_access_protected_route(app_client):
    setup_response = app_client.post(
        "/api/setup",
        json={
            "full_name": "Marcin Petkowicz",
            "date_of_birth": "1986-03-26",
            "email": "marcin@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    assert setup_response.status_code == 200

    login_response = app_client.post(
        "/api/login",
        json={"email": "marcin@example.com", "password": "correct-horse-battery-staple"},
    )
    assert login_response.status_code == 200
    assert "lifeboard_session" in login_response.cookies

    modules_response = app_client.get("/api/modules")
    assert modules_response.status_code == 200
    assert "echo" in modules_response.json()


def test_setup_twice_returns_409(app_client):
    payload = {
        "full_name": "Marcin Petkowicz",
        "date_of_birth": "1986-03-26",
        "email": "marcin@example.com",
        "password": "correct-horse-battery-staple",
    }
    app_client.post("/api/setup", json=payload)
    second = app_client.post("/api/setup", json=payload)
    assert second.status_code == 409


def test_login_with_wrong_password_returns_401(app_client):
    app_client.post(
        "/api/setup",
        json={
            "full_name": "Marcin Petkowicz",
            "date_of_birth": "1986-03-26",
            "email": "marcin@example.com",
            "password": "correct-horse-battery-staple",
        },
    )

    response = app_client.post(
        "/api/login", json={"email": "marcin@example.com", "password": "wrong"}
    )
    assert response.status_code == 401


def test_full_integration_lifecycle_save_sync_then_module_shows_data(app_client):
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

    save_response = app_client.post(
        "/api/integrations/echo/credentials", json={"value": "hello-world"}
    )
    assert save_response.status_code == 200

    sync_response = app_client.post("/api/integrations/echo/sync-now")
    assert sync_response.status_code == 200

    data_response = app_client.get("/api/modules/echo/data")
    assert data_response.status_code == 200
    assert data_response.json()["primary_value"] == "hello-world"


def test_save_credentials_with_failing_test_connection_returns_400(app_client):
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

    # echo integration's test_connection requires a non-empty "value"
    response = app_client.post("/api/integrations/echo/credentials", json={"value": ""})
    assert response.status_code == 400


def test_logout_then_protected_route_returns_401(app_client):
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
    app_client.post("/api/logout")

    response = app_client.get("/api/modules")
    assert response.status_code == 401


def test_dashboard_layout_save_then_load_round_trips(app_client):
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

    layout = [{"module_id": "echo", "enabled": True, "position": 0, "refresh_seconds": 30}]
    save_response = app_client.post("/api/dashboard", json={"modules": layout})
    assert save_response.status_code == 200

    load_response = app_client.get("/api/dashboard")
    assert load_response.status_code == 200
    assert load_response.json()["modules"] == layout
