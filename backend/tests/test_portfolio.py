"""Tests for the built-in portfolio integration (NBP FX + CoinGecko
crypto prices, keyless) + portfolio module. Network calls are mocked —
no real network access needed. See backend/integrations/portfolio/sync.py
for why this deliberately covers only crypto+cash, not stocks.
"""
import json
import sqlite3
from io import BytesIO
from unittest.mock import patch

import pytest


def _response(payload):
    return BytesIO(json.dumps(payload).encode("utf-8"))


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


_NBP_TABLE = [{"rates": [{"code": "USD", "mid": 3.90}, {"code": "EUR", "mid": 4.30}]}]
_COINGECKO_PRICES = {"ethereum": {"usd": 2500.0}}

_HOLDINGS_JSON = json.dumps(
    [
        {"kind": "crypto", "symbol": "ETH", "coingecko_id": "ethereum", "quantity": 2.0, "cost_basis_pln": 15000},
        {"kind": "cash", "symbol": "PLN cash", "amount_pln": 500.0},
    ]
)


def _mock_urlopen_sequence(*payloads):
    iterator = iter(payloads)

    def _side_effect(*args, **kwargs):
        response = _response(next(iterator))
        mock_cm = type("MockCM", (), {"__enter__": lambda self: response, "__exit__": lambda self, *a: None})()
        return mock_cm

    return _side_effect


def test_portfolio_test_connection_true_with_valid_holdings(db):
    from backend.integrations.portfolio.sync import Sync

    with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(_NBP_TABLE)):
        assert Sync().test_connection({"holdings_json": _HOLDINGS_JSON}) is True


def test_portfolio_test_connection_false_without_holdings(db):
    from backend.integrations.portfolio.sync import Sync

    assert Sync().test_connection({"holdings_json": ""}) is False


def test_portfolio_test_connection_false_with_malformed_json(db):
    from backend.integrations.portfolio.sync import Sync

    assert Sync().test_connection({"holdings_json": "not json"}) is False


def test_portfolio_sync_writes_holdings_with_live_prices(db):
    from backend.integrations.portfolio.sync import Sync

    with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(_NBP_TABLE, _COINGECKO_PRICES)):
        Sync().sync({"holdings_json": _HOLDINGS_JSON}, db)

    eth_row = db.execute(
        "SELECT symbol, kind, quantity, price_usd, value_pln, cost_basis_pln FROM portfolio_holdings WHERE symbol = 'ETH'"
    ).fetchone()
    # ETH: 2.0 * 2500 USD * 3.90 PLN/USD = 19500 PLN
    assert eth_row == ("ETH", "crypto", 2.0, 2500.0, 19500.0, 15000)

    cash_row = db.execute(
        "SELECT symbol, kind, value_pln FROM portfolio_holdings WHERE symbol = 'PLN cash'"
    ).fetchone()
    assert cash_row == ("PLN cash", "cash", 500.0)


def test_portfolio_sync_replaces_removed_holdings_not_just_upserts(db):
    from backend.integrations.portfolio.sync import Sync

    with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(_NBP_TABLE, _COINGECKO_PRICES)):
        Sync().sync({"holdings_json": _HOLDINGS_JSON}, db)

    smaller_holdings = json.dumps([{"kind": "cash", "symbol": "PLN cash", "amount_pln": 500.0}])
    with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(_NBP_TABLE, _COINGECKO_PRICES)):
        Sync().sync({"holdings_json": smaller_holdings}, db)

    count = db.execute("SELECT COUNT(*) FROM portfolio_holdings").fetchone()[0]
    assert count == 1
    remaining = db.execute("SELECT symbol FROM portfolio_holdings").fetchone()[0]
    assert remaining == "PLN cash"


def test_portfolio_sync_raises_on_network_error(db):
    from backend.integrations.portfolio.sync import Sync

    with patch("urllib.request.urlopen", side_effect=OSError("network down")):
        with pytest.raises(OSError):
            Sync().sync({"holdings_json": _HOLDINGS_JSON}, db)


def test_portfolio_provider_no_data_before_any_sync(db):
    from backend.modules.portfolio.provider import Provider

    result = Provider().get_data(db)
    assert result["primary_value"] == "no data yet"
    assert result["status"] == "neutral"


def test_portfolio_provider_sums_total_and_shows_gain(db):
    from backend.integrations.portfolio.sync import Sync
    from backend.modules.portfolio.provider import Provider

    with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(_NBP_TABLE, _COINGECKO_PRICES)):
        Sync().sync({"holdings_json": _HOLDINGS_JSON}, db)

    result = Provider().get_data(db)
    # total = 19500 (ETH) + 500 (cash) = 20000; cost = 15000 + 500 = 15500
    assert result["primary_value"] == "20,000"
    assert result["status"] == "ok"
