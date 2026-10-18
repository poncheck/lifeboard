"""Tests for the built-in echo module/integration pair — the smoke-test
proving the full integration lifecycle works end to end.
"""
import sqlite3

import pytest


@pytest.fixture
def db(tmp_path):
    conn = sqlite3.connect(tmp_path / "test.db")
    yield conn
    conn.close()


def test_provider_before_any_sync_returns_no_data_placeholder(db):
    import importlib.util
    from pathlib import Path

    provider_path = Path(__file__).resolve().parent.parent / "modules" / "echo" / "provider.py"
    spec = importlib.util.spec_from_file_location("echo_provider_test", provider_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    provider = mod.Provider()
    result = provider.get_data(db)

    assert result["primary_value"] == "no data yet"
    assert result["status"] == "neutral"


def test_sync_then_provider_returns_synced_value(db):
    import importlib.util
    from pathlib import Path

    sync_path = Path(__file__).resolve().parent.parent / "integrations" / "echo" / "sync.py"
    spec = importlib.util.spec_from_file_location("echo_sync_test", sync_path)
    sync_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sync_mod)

    provider_path = Path(__file__).resolve().parent.parent / "modules" / "echo" / "provider.py"
    spec2 = importlib.util.spec_from_file_location("echo_provider_test2", provider_path)
    provider_mod = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(provider_mod)

    sync = sync_mod.Sync()
    sync.sync({"value": "hello"}, db)

    provider = provider_mod.Provider()
    result = provider.get_data(db)

    assert result["primary_value"] == "hello"
    assert result["status"] == "ok"
