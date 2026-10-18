"""Tests for backend.core.base — the Integration and DashboardModule ABCs."""
import pytest


def test_dashboard_module_cannot_be_instantiated_without_get_data():
    from backend.core.base import DashboardModule

    class Incomplete(DashboardModule):
        pass

    with pytest.raises(TypeError):
        Incomplete()


def test_dashboard_module_subclass_with_get_data_instantiates():
    from backend.core.base import DashboardModule

    class Complete(DashboardModule):
        def get_data(self, db):
            return {"title": "Test", "primary_value": "1", "status": "ok"}

    instance = Complete()
    result = instance.get_data(db=None)
    assert result["title"] == "Test"


def test_integration_cannot_be_instantiated_without_required_methods():
    from backend.core.base import Integration

    class Incomplete(Integration):
        pass

    with pytest.raises(TypeError):
        Incomplete()


def test_integration_subclass_with_both_methods_instantiates():
    from backend.core.base import Integration

    class Complete(Integration):
        def test_connection(self, credentials):
            return True

        def sync(self, credentials, db):
            pass

    instance = Complete()
    assert instance.test_connection(credentials={}) is True
