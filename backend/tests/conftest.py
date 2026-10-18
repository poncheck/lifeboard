"""Shared pytest fixtures for backend/tests.

app_client: a FastAPI TestClient wired to temp module/integration dirs
containing only the `echo` test pair — used by tests that don't care
about the real built-in modules (test_api.py's Phase 1 flow).

real_app_client: a FastAPI TestClient wired to the actual
backend/modules and backend/integrations directories, so tests can
exercise the real built-ins (clock, echo, intervals_icu, traccar,
weather, training_readiness, location, nutrition) end to end through
the API, same as a real deployment would discover them.
"""
import json
import textwrap
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

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


@pytest.fixture
def real_app_client(tmp_path, monkeypatch):
    monkeypatch.setenv("LIFEBOARD_SECRET_KEY", "test-secret-key-long-enough-for-tests")
    monkeypatch.setenv("LIFEBOARD_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LIFEBOARD_MODULES_DIR", str(_REPO_ROOT / "backend" / "modules"))
    monkeypatch.setenv("LIFEBOARD_INTEGRATIONS_DIR", str(_REPO_ROOT / "backend" / "integrations"))
    monkeypatch.setenv("LIFEBOARD_LAYOUT_PATH", str(tmp_path / "dashboard.yaml"))

    from backend.main import create_app

    app = create_app()
    return TestClient(app)
