"""Reads/writes the user's dashboard layout (config/dashboard.yaml)."""
from pathlib import Path

import yaml


class LayoutStore:
    def __init__(self, path: Path):
        self._path = Path(path)

    def load(self) -> list[dict]:
        if not self._path.is_file():
            return []
        data = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
        return data.get("modules", [])

    def save(self, layout: list[dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            yaml.safe_dump({"modules": layout}, sort_keys=False), encoding="utf-8"
        )
