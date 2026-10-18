"""Tests for backend.core.integration_registry — discovers integrations
from backend/integrations/*/integration.json + sync.py. Same safety rule
as module_registry: a broken integration is logged and skipped, never
crashes the app.
"""
import json
import textwrap

import pytest


@pytest.fixture
def integrations_dir(tmp_path):
    d = tmp_path / "integrations"
    d.mkdir()
    return d


def _write_integration(integrations_dir, integration_id, manifest: dict, sync_code: str):
    int_dir = integrations_dir / integration_id
    int_dir.mkdir()
    (int_dir / "integration.json").write_text(json.dumps(manifest))
    (int_dir / "sync.py").write_text(textwrap.dedent(sync_code))


def _valid_manifest(integration_id="test_integration"):
    return {
        "id": integration_id,
        "name": "Test Integration",
        "description": "A test integration",
        "credential_fields": [{"key": "api_key", "label": "API Key", "secret": True}],
        "sync_interval_seconds": 900,
    }


ECHO_SYNC = """
from backend.core.base import Integration

class Sync(Integration):
    def test_connection(self, credentials):
        return credentials.get("api_key") == "valid-key"

    def sync(self, credentials, db):
        pass
"""


def test_discovers_a_valid_integration(integrations_dir):
    from backend.core.integration_registry import IntegrationRegistry

    _write_integration(integrations_dir, "echo", _valid_manifest("echo"), ECHO_SYNC)

    registry = IntegrationRegistry(integrations_dir)
    registry.discover()

    assert "echo" in registry.list_integrations()


def test_test_connection_delegates_to_sync_class(integrations_dir):
    from backend.core.integration_registry import IntegrationRegistry

    _write_integration(integrations_dir, "echo", _valid_manifest("echo"), ECHO_SYNC)

    registry = IntegrationRegistry(integrations_dir)
    registry.discover()

    assert registry.test_connection("echo", {"api_key": "valid-key"}) is True
    assert registry.test_connection("echo", {"api_key": "wrong-key"}) is False


def test_integration_with_broken_manifest_is_skipped_not_crashed(integrations_dir):
    from backend.core.integration_registry import IntegrationRegistry

    broken_dir = integrations_dir / "broken"
    broken_dir.mkdir()
    (broken_dir / "integration.json").write_text("{ not valid json")
    (broken_dir / "sync.py").write_text("class Sync: pass")

    _write_integration(integrations_dir, "good", _valid_manifest("good"), ECHO_SYNC)

    registry = IntegrationRegistry(integrations_dir)
    registry.discover()  # must not raise

    assert "good" in registry.list_integrations()
    assert "broken" not in registry.list_integrations()


def test_sync_catches_raising_sync_method_does_not_propagate(integrations_dir):
    from backend.core.integration_registry import IntegrationRegistry

    raising_sync = """
    from backend.core.base import Integration

    class Sync(Integration):
        def test_connection(self, credentials):
            return True

        def sync(self, credentials, db):
            raise RuntimeError("platform is down")
    """
    _write_integration(integrations_dir, "flaky", _valid_manifest("flaky"), raising_sync)

    registry = IntegrationRegistry(integrations_dir)
    registry.discover()

    # Must not raise — sync() errors are caught and logged, scheduler retries later
    registry.sync("flaky", credentials={}, db=None)


def test_test_connection_for_unknown_integration_returns_false(integrations_dir):
    from backend.core.integration_registry import IntegrationRegistry

    registry = IntegrationRegistry(integrations_dir)
    registry.discover()

    assert registry.test_connection("does_not_exist", {}) is False


def test_list_integrations_includes_manifest_metadata(integrations_dir):
    from backend.core.integration_registry import IntegrationRegistry

    _write_integration(integrations_dir, "echo", _valid_manifest("echo"), ECHO_SYNC)

    registry = IntegrationRegistry(integrations_dir)
    registry.discover()

    manifest = registry.list_integrations()["echo"]
    assert manifest["name"] == "Test Integration"
    assert manifest["sync_interval_seconds"] == 900
