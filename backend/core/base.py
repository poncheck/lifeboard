"""Base ABCs for LifeBoard's module/integration contract. See
docs/ARCHITECTURE.md for the full design rationale."""
from abc import ABC, abstractmethod
from typing import Any


class DashboardModule(ABC):
    """The display half of a module. Reads from LifeBoard's own database
    and returns a small dict matching the generic card schema (or ships a
    custom frontend renderer)."""

    @abstractmethod
    def get_data(self, db: Any) -> dict:
        """Called on each refresh tick. Must be fast (<1s) and must not
        raise — catch your own errors and return {"error": "..."} so one
        broken module never takes down the dashboard."""
        raise NotImplementedError


class Integration(ABC):
    """The data-collection half of a module. Pulls from a third-party
    platform on a schedule and writes normalized rows into LifeBoard's
    own database."""

    @abstractmethod
    def test_connection(self, credentials: dict) -> bool:
        """Cheap, read-only check that the given credentials work.
        Called from the admin panel's 'Test & Save' button. Must not
        write any data."""
        raise NotImplementedError

    @abstractmethod
    def sync(self, credentials: dict, db: Any) -> None:
        """Called on the integration's sync_interval_seconds by the
        scheduler, and on-demand via 'Sync now'. Must not raise — catch
        your own errors, log them, and let the scheduler retry next
        tick. Must be idempotent (upsert on a natural key)."""
        raise NotImplementedError
