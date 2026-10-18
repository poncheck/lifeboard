"""The echo integration: a fake 'platform' used only to prove the
credential -> test_connection -> sync -> display pipeline works end to
end without needing a real Intervals.icu/Traccar account. See
docs/MODULE_AUTHORING.md for the copy-pasteable version of this pattern.
"""
from backend.core.base import Integration


class Sync(Integration):
    def test_connection(self, credentials):
        return bool(credentials.get("value"))

    def sync(self, credentials, db):
        db.execute(
            "CREATE TABLE IF NOT EXISTS echo_data (id INTEGER PRIMARY KEY, value TEXT)"
        )
        db.execute("INSERT INTO echo_data (value) VALUES (?)", (credentials.get("value"),))
        db.commit()
