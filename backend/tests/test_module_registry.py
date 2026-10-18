"""Tests for backend.core.module_registry — discovers dashboard modules
from backend/modules/*/module.json + provider.py. Per docs/ARCHITECTURE.md:
a broken manifest or import error is logged and skipped, never crashes
the whole app.
"""
import json
import textwrap

import pytest


@pytest.fixture
def modules_dir(tmp_path):
    d = tmp_path / "modules"
    d.mkdir()
    return d


def _write_module(modules_dir, module_id, manifest: dict, provider_code: str):
    mod_dir = modules_dir / module_id
    mod_dir.mkdir()
    (mod_dir / "module.json").write_text(json.dumps(manifest))
    (mod_dir / "provider.py").write_text(textwrap.dedent(provider_code))


def _valid_manifest(module_id="test_module"):
    return {
        "id": module_id,
        "name": "Test Module",
        "description": "A test module",
        "icon": "test",
        "category": "system",
        "default_refresh_seconds": 30,
        "grid_size": "1x1",
        "requires_integration": None,
    }


def test_discovers_a_valid_module(modules_dir):
    from backend.core.module_registry import ModuleRegistry

    _write_module(
        modules_dir,
        "echo",
        _valid_manifest("echo"),
        """
        from backend.core.base import DashboardModule

        class Provider(DashboardModule):
            def get_data(self, db):
                return {"title": "Echo", "primary_value": "ok", "status": "ok"}
        """,
    )

    registry = ModuleRegistry(modules_dir)
    registry.discover()

    assert "echo" in registry.list_modules()


def test_get_data_from_discovered_module_returns_expected_payload(modules_dir):
    from backend.core.module_registry import ModuleRegistry

    _write_module(
        modules_dir,
        "echo",
        _valid_manifest("echo"),
        """
        from backend.core.base import DashboardModule

        class Provider(DashboardModule):
            def get_data(self, db):
                return {"title": "Echo", "primary_value": "ok", "status": "ok"}
        """,
    )

    registry = ModuleRegistry(modules_dir)
    registry.discover()

    result = registry.get_module_data("echo", db=None)
    assert result == {"title": "Echo", "primary_value": "ok", "status": "ok"}


def test_module_with_broken_manifest_is_skipped_not_crashed(modules_dir):
    from backend.core.module_registry import ModuleRegistry

    mod_dir = modules_dir / "broken"
    mod_dir.mkdir()
    (mod_dir / "module.json").write_text("{ not valid json !!!")
    (mod_dir / "provider.py").write_text("class Provider: pass")

    # Also add one valid module alongside the broken one
    _write_module(
        modules_dir,
        "good",
        _valid_manifest("good"),
        """
        from backend.core.base import DashboardModule

        class Provider(DashboardModule):
            def get_data(self, db):
                return {"title": "Good", "primary_value": "1", "status": "ok"}
        """,
    )

    registry = ModuleRegistry(modules_dir)
    registry.discover()  # must not raise

    assert "good" in registry.list_modules()
    assert "broken" not in registry.list_modules()


def test_module_with_import_error_in_provider_is_skipped_not_crashed(modules_dir):
    from backend.core.module_registry import ModuleRegistry

    _write_module(
        modules_dir,
        "broken_import",
        _valid_manifest("broken_import"),
        "import this_module_does_not_exist_anywhere",
    )
    _write_module(
        modules_dir,
        "good",
        _valid_manifest("good"),
        """
        from backend.core.base import DashboardModule

        class Provider(DashboardModule):
            def get_data(self, db):
                return {"title": "Good", "primary_value": "1", "status": "ok"}
        """,
    )

    registry = ModuleRegistry(modules_dir)
    registry.discover()  # must not raise

    assert "good" in registry.list_modules()
    assert "broken_import" not in registry.list_modules()


def test_get_module_data_catches_raising_provider_returns_error_payload(modules_dir):
    from backend.core.module_registry import ModuleRegistry

    _write_module(
        modules_dir,
        "raiser",
        _valid_manifest("raiser"),
        """
        from backend.core.base import DashboardModule

        class Provider(DashboardModule):
            def get_data(self, db):
                raise RuntimeError("boom")
        """,
    )

    registry = ModuleRegistry(modules_dir)
    registry.discover()

    result = registry.get_module_data("raiser", db=None)
    assert "error" in result


def test_get_module_data_for_unknown_module_returns_error_payload(modules_dir):
    from backend.core.module_registry import ModuleRegistry

    registry = ModuleRegistry(modules_dir)
    registry.discover()

    result = registry.get_module_data("does_not_exist", db=None)
    assert "error" in result


def test_list_modules_includes_manifest_metadata(modules_dir):
    from backend.core.module_registry import ModuleRegistry

    _write_module(
        modules_dir,
        "echo",
        _valid_manifest("echo"),
        """
        from backend.core.base import DashboardModule

        class Provider(DashboardModule):
            def get_data(self, db):
                return {"title": "Echo", "primary_value": "ok", "status": "ok"}
        """,
    )

    registry = ModuleRegistry(modules_dir)
    registry.discover()

    manifest = registry.list_modules()["echo"]
    assert manifest["name"] == "Test Module"
    assert manifest["default_refresh_seconds"] == 30
