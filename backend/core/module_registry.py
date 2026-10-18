"""Discovers and safely loads dashboard modules from backend/modules/.

Per docs/ARCHITECTURE.md: a broken manifest or an import error is logged
and that module is skipped — the registry never lets one bad folder take
down the whole app.
"""
import importlib.util
import json
import logging
from pathlib import Path
from typing import Any

from backend.core.base import DashboardModule

logger = logging.getLogger(__name__)


class ModuleRegistry:
    def __init__(self, modules_dir: Path):
        self._modules_dir = Path(modules_dir)
        self._manifests: dict[str, dict] = {}
        self._providers: dict[str, DashboardModule] = {}

    def discover(self) -> None:
        """Scan modules_dir for <module_id>/module.json + provider.py.
        Never raises — a bad module is logged and skipped."""
        self._manifests.clear()
        self._providers.clear()

        if not self._modules_dir.is_dir():
            return

        for module_dir in sorted(self._modules_dir.iterdir()):
            if not module_dir.is_dir():
                continue
            self._try_load_module(module_dir)

    def _try_load_module(self, module_dir: Path) -> None:
        module_id = module_dir.name
        manifest_path = module_dir / "module.json"
        provider_path = module_dir / "provider.py"

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Skipping module %r: invalid module.json (%s)", module_id, exc)
            return

        if not provider_path.is_file():
            logger.warning("Skipping module %r: no provider.py found", module_id)
            return

        try:
            spec = importlib.util.spec_from_file_location(
                f"lifeboard_module_{module_id}", provider_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"could not load spec for {provider_path}")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            provider_cls = getattr(mod, "Provider")
            provider_instance = provider_cls()
        except Exception as exc:  # noqa: BLE001 — intentionally broad, see docstring
            logger.warning("Skipping module %r: failed to load provider.py (%s)", module_id, exc)
            return

        self._manifests[module_id] = manifest
        self._providers[module_id] = provider_instance

    def list_modules(self) -> dict[str, dict]:
        return dict(self._manifests)

    def get_module_data(self, module_id: str, db: Any) -> dict:
        provider = self._providers.get(module_id)
        if provider is None:
            return {"error": f"Module '{module_id}' is not available."}

        try:
            return provider.get_data(db)
        except Exception as exc:  # noqa: BLE001 — a module's bug must not take down the API
            logger.warning("Module %r raised during get_data: %s", module_id, exc)
            return {"error": f"Module '{module_id}' failed to load data."}
