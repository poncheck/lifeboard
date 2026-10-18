"""The portfolio integration: crypto + cash holdings, priced live via
NBP (PLN FX rates, keyless) and CoinGecko (crypto spot prices,
keyless). Per docs/ARCHITECTURE.md's Phase 6 note, this is deliberately
NOT a generic "connect your brokerage" integration — stock positions
(the Tradegate/bankier-style sources in the original reference script)
need either fragile HTML scraping or a headless browser, which doesn't
fit "reliable, anyone can reuse this" the way NBP/CoinGecko do. Holdings
are entered as JSON through the admin panel's credential form (a
`secret: true` field, encrypted at rest) — never hardcoded in this
file, since this repo is public and holdings are financial data.

Holdings JSON shape (array of objects), two kinds:
    [
      {"kind": "crypto", "symbol": "ETH", "coingecko_id": "ethereum",
       "quantity": 1.262, "cost_basis_pln": 5000},
      {"kind": "cash", "symbol": "PLN cash", "amount_pln": 172.55}
    ]
"""
import json
import urllib.parse
import urllib.request

from backend.core.base import Integration

_NBP_RATES_URL = "https://api.nbp.pl/api/exchangerates/tables/A/?format=json"
_COINGECKO_PRICE_URL = "https://api.coingecko.com/api/v3/simple/price"


def _fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read())


def _fetch_usd_pln_rate() -> float:
    table = _fetch_json(_NBP_RATES_URL)
    rates = {entry["code"]: entry["mid"] for entry in table[0]["rates"]}
    return rates["USD"]


def _fetch_crypto_prices_usd(coingecko_ids: list[str]) -> dict[str, float]:
    if not coingecko_ids:
        return {}
    ids_param = urllib.parse.quote(",".join(sorted(set(coingecko_ids))))
    url = f"{_COINGECKO_PRICE_URL}?ids={ids_param}&vs_currencies=usd"
    data = _fetch_json(url)
    return {coin_id: entry.get("usd", 0.0) for coin_id, entry in data.items()}


def _parse_holdings(holdings_json: str) -> list[dict]:
    try:
        holdings = json.loads(holdings_json)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(holdings, list):
        return []
    return [h for h in holdings if isinstance(h, dict) and h.get("symbol")]


class Sync(Integration):
    def test_connection(self, credentials: dict) -> bool:
        holdings_json = credentials.get("holdings_json")
        if not holdings_json:
            return False
        holdings = _parse_holdings(holdings_json)
        if not holdings:
            return False
        try:
            # Cheap read-only check: just confirm NBP is reachable —
            # don't bother hitting CoinGecko here too, one live API
            # check is enough to validate "credentials" (really just
            # well-formed holdings JSON) work.
            _fetch_usd_pln_rate()
            return True
        except Exception:
            return False

    def sync(self, credentials: dict, db) -> None:
        holdings_json = credentials.get("holdings_json")
        if not holdings_json:
            return
        holdings = _parse_holdings(holdings_json)
        if not holdings:
            return

        # Raising on failure is intentional — see backend/core/base.py's
        # updated Integration.sync() contract.
        usd_pln = _fetch_usd_pln_rate()

        crypto_ids = [h["coingecko_id"] for h in holdings if h.get("kind") == "crypto" and h.get("coingecko_id")]
        prices_usd = _fetch_crypto_prices_usd(crypto_ids)

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS portfolio_holdings (
                symbol TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                quantity REAL,
                price_usd REAL,
                value_pln REAL NOT NULL,
                cost_basis_pln REAL
            )
            """
        )
        # Full replace each sync (not a per-row upsert): a holding
        # removed from the JSON must disappear from the total, which a
        # row-by-row upsert wouldn't do on its own.
        db.execute("DELETE FROM portfolio_holdings")

        for holding in holdings:
            symbol = holding["symbol"]
            kind = holding.get("kind", "cash")

            if kind == "crypto":
                quantity = float(holding.get("quantity", 0))
                price_usd = prices_usd.get(holding.get("coingecko_id", ""), 0.0)
                value_pln = quantity * price_usd * usd_pln
                cost_basis_pln = holding.get("cost_basis_pln")
            else:
                quantity = None
                price_usd = None
                value_pln = float(holding.get("amount_pln", 0))
                cost_basis_pln = holding.get("cost_basis_pln", value_pln)

            db.execute(
                "INSERT INTO portfolio_holdings "
                "(symbol, kind, quantity, price_usd, value_pln, cost_basis_pln) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (symbol, kind, quantity, price_usd, value_pln, cost_basis_pln),
            )
        db.commit()
