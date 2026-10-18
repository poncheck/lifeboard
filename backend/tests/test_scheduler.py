"""Tests for backend.core.scheduler.IntegrationScheduler.

Per docs/ARCHITECTURE.md Phase 1: a background scheduler calls each
configured integration's sync() on its own sync_interval_seconds.
"""
import sqlite3
import time

from backend.core.integration_registry import IntegrationRegistry
from backend.core.scheduler import IntegrationScheduler


class _StubSync:
    def __init__(self):
        self.sync_calls: list[dict] = []

    def test_connection(self, credentials):
        return True

    def sync(self, credentials, db):
        self.sync_calls.append(dict(credentials))


def _registry_with_stub(integration_id: str, stub: _StubSync) -> IntegrationRegistry:
    registry = IntegrationRegistry(integrations_dir="/nonexistent")
    # Bypass real discovery (no files on disk needed for this test) by
    # populating the registry's internal maps directly.
    registry._manifests[integration_id] = {
        "id": integration_id,
        "name": integration_id,
        "sync_interval_seconds": 1,
    }
    registry._syncs[integration_id] = stub
    return registry


def test_schedule_runs_sync_on_interval():
    stub = _StubSync()
    registry = _registry_with_stub("demo", stub)
    scheduler = IntegrationScheduler(
        integration_registry=registry,
        load_credentials=lambda integration_id: {"key": "value"},
        open_db=lambda: sqlite3.connect(":memory:"),
    )
    scheduler.start()
    try:
        scheduler.schedule("demo", sync_interval_seconds=1)
        time.sleep(2.5)
        assert len(stub.sync_calls) >= 2
        assert stub.sync_calls[0] == {"key": "value"}
    finally:
        scheduler.shutdown()


def test_schedule_skips_run_when_no_credentials():
    stub = _StubSync()
    registry = _registry_with_stub("demo", stub)
    scheduler = IntegrationScheduler(
        integration_registry=registry,
        load_credentials=lambda integration_id: {},
        open_db=lambda: sqlite3.connect(":memory:"),
    )
    scheduler.start()
    try:
        scheduler.schedule("demo", sync_interval_seconds=1)
        time.sleep(1.5)
        assert stub.sync_calls == []
    finally:
        scheduler.shutdown()


def test_unschedule_stops_future_runs():
    stub = _StubSync()
    registry = _registry_with_stub("demo", stub)
    scheduler = IntegrationScheduler(
        integration_registry=registry,
        load_credentials=lambda integration_id: {"key": "value"},
        open_db=lambda: sqlite3.connect(":memory:"),
    )
    scheduler.start()
    try:
        scheduler.schedule("demo", sync_interval_seconds=1)
        time.sleep(1.5)
        calls_before = len(stub.sync_calls)
        assert calls_before >= 1

        scheduler.unschedule("demo")
        time.sleep(1.5)
        assert len(stub.sync_calls) == calls_before
        assert "demo" not in scheduler.scheduled_integration_ids()
    finally:
        scheduler.shutdown()


def test_unschedule_is_safe_when_nothing_scheduled():
    stub = _StubSync()
    registry = _registry_with_stub("demo", stub)
    scheduler = IntegrationScheduler(
        integration_registry=registry,
        load_credentials=lambda integration_id: {},
        open_db=lambda: sqlite3.connect(":memory:"),
    )
    scheduler.start()
    try:
        scheduler.unschedule("never-scheduled")  # must not raise
    finally:
        scheduler.shutdown()


def test_schedule_replaces_existing_job_instead_of_duplicating():
    stub = _StubSync()
    registry = _registry_with_stub("demo", stub)
    scheduler = IntegrationScheduler(
        integration_registry=registry,
        load_credentials=lambda integration_id: {"key": "value"},
        open_db=lambda: sqlite3.connect(":memory:"),
    )
    scheduler.start()
    try:
        scheduler.schedule("demo", sync_interval_seconds=1)
        scheduler.schedule("demo", sync_interval_seconds=1)
        assert scheduler.scheduled_integration_ids() == {"demo"}
    finally:
        scheduler.shutdown()
