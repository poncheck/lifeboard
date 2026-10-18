"""Tests for backend.core.layout_store — reads/writes config/dashboard.yaml."""
import pytest


@pytest.fixture
def layout_path(tmp_path):
    return tmp_path / "dashboard.yaml"


def test_load_returns_empty_list_when_file_does_not_exist(layout_path):
    from backend.core.layout_store import LayoutStore

    store = LayoutStore(layout_path)
    assert store.load() == []


def test_save_then_load_round_trips(layout_path):
    from backend.core.layout_store import LayoutStore

    store = LayoutStore(layout_path)
    layout = [
        {"module_id": "clock", "enabled": True, "position": 0, "refresh_seconds": 1},
        {"module_id": "echo", "enabled": False, "position": 1, "refresh_seconds": 30},
    ]

    store.save(layout)
    loaded = store.load()

    assert loaded == layout


def test_save_overwrites_previous_layout(layout_path):
    from backend.core.layout_store import LayoutStore

    store = LayoutStore(layout_path)
    store.save([{"module_id": "clock", "enabled": True, "position": 0, "refresh_seconds": 1}])
    store.save([{"module_id": "echo", "enabled": True, "position": 0, "refresh_seconds": 30}])

    loaded = store.load()
    assert len(loaded) == 1
    assert loaded[0]["module_id"] == "echo"
