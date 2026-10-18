"""Discovers and safely loads integrations from backend/integrations/.

Mirrors module_registry.py's safety rule: a broken manifest or an import
error is logged and that integration is skipped — the registry never
lets one bad folder take down the whole app. sync() exceptions are also
caught here (the scheduler retries on the next tick instead of crashing).
"""
import importlib.util
import json
import logging
from pathlib import Path
from typing import Any

from backend.core.base import Integration

logger = logging.getLogger(__name__)


class IntegrationRegistry:
    def __init__(self, integrations_dir: Path):
        self._integrations_dir = Path(integrations_dir)
        self._manifests: dict[str, dict] = {}
        self._syncs: dict[str, Integration] = {}

    def discover(self) -> None:
        self._manifests.clear()
        self._syncs.clear()

        if not self._integrations_dir.is_dir():
            return

        for integration_dir in sorted(self._integrations_dir.iterdir()):
            if not integration_dir.is_dir():
                continue
            self._try_load_integration(integration_dir)

    def _try_load_integration(self, integration_dir: Path) -> None:
        integration_id = integration_dir.name
        manifest_path = integration_dir / "integration.json"
        sync_path = integration_dir / "sync.py"

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(
                "Skipping integration %r: invalid integration.json (%s)", integration_id, exc
            )
            return

        if not sync_path.is_file():
            logger.warning("Skipping integration %r: no sync.py found", integration_id)
            return

        try:
            spec = importlib.util.spec_from_file_location(
                f"lifeboard_integration_{integration_id}", sync_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"could not load spec for {sync_path}")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            sync_cls = getattr(mod, "Sync")
            sync_instance = sync_cls()
        except Exception as exc:  # noqa: BLE001 — intentionally broad, see docstring
            logger.warning(
                "Skipping integration %r: failed to load sync.py (%s)", integration_id, exc
            )
            return

        self._manifests[integration_id] = manifest
        self._syncs[integration_id] = sync_instance

    def list_integrations(self) -> dict[str, dict]:
        return dict(self._manifests)

    def test_connection(self, integration_id: str, credentials: dict) -> bool:
        sync = self._syncs.get(integration_id)
        if sync is None:
            return False
        try:
            return bool(sync.test_connection(credentials))
        except Exception as exc:  # noqa: BLE001 — a bad integration must not crash the API
            logger.warning("Integration %r raised during test_connection: %s", integration_id, exc)
            return False

    def sync(self, integration_id: str, credentials: dict, db: Any) -> tuple[bool, str | None]:
        """Runs the integration's sync(). Never raises. Returns
        (success, error_message) so callers (main.py, the scheduler) can
        surface 'last synced at' / 'last error' status without this
        registry's core 'never crash' contract changing."""
        sync = self._syncs.get(integration_id)
        if sync is None:
            logger.warning("Cannot sync unknown integration %r", integration_id)
            return False, "Unknown integration."
        try:
            sync.sync(credentials, db)
            return True, None
        except Exception as exc:  # noqa: BLE001 — scheduler retries next tick, never crashes
            logger.warning("Integration %r raised during sync: %s", integration_id, exc)
            return False, str(exc)
