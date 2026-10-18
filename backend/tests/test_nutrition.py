"""Tests for the built-in nutrition module (manual entry, no
integration) and backend.main's /api/nutrition/entries endpoints.
"""
import sqlite3

import pytest


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


def test_nutrition_provider_zero_before_any_entries(db):
    from backend.modules.nutrition.provider import Provider

    result = Provider().get_data(db)
    assert result["primary_value"] == "0"
    assert result["status"] == "neutral"


def test_nutrition_provider_sums_todays_entries(db):
    from datetime import date, datetime, timezone

    from backend.modules.nutrition.provider import Provider

    db.execute(
        "CREATE TABLE nutrition_log (id INTEGER PRIMARY KEY AUTOINCREMENT, day TEXT NOT NULL, "
        "logged_at TEXT NOT NULL, name TEXT NOT NULL, kcal REAL NOT NULL, protein_g REAL NOT NULL DEFAULT 0, "
        "carbs_g REAL NOT NULL DEFAULT 0, fat_g REAL NOT NULL DEFAULT 0)"
    )
    today = date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "INSERT INTO nutrition_log (day, logged_at, name, kcal, protein_g, carbs_g, fat_g) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (today, now, "Breakfast", 400, 20, 50, 10),
    )
    db.execute(
        "INSERT INTO nutrition_log (day, logged_at, name, kcal, protein_g, carbs_g, fat_g) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (today, now, "Lunch", 600, 30, 70, 15),
    )
    db.commit()

    result = Provider().get_data(db)
    assert result["primary_value"] == "1000"
    assert result["status"] == "ok"
    lines_by_label = {line["label"]: line["value"] for line in result["lines"]}
    assert lines_by_label["Meals logged"] == "2"


def test_log_nutrition_entry_then_appears_in_module_data(real_app_client):
    app_client = real_app_client
    app_client.post(
        "/api/setup",
        json={
            "full_name": "Marcin Petkowicz",
            "date_of_birth": "1986-03-26",
            "email": "marcin@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    app_client.post(
        "/api/login",
        json={"email": "marcin@example.com", "password": "correct-horse-battery-staple"},
    )

    response = app_client.post(
        "/api/nutrition/entries",
        json={"name": "Breakfast", "kcal": 500, "protein_g": 25, "carbs_g": 60, "fat_g": 12},
    )
    assert response.status_code == 200

    entries = app_client.get("/api/nutrition/entries").json()
    assert len(entries) == 1
    assert entries[0]["name"] == "Breakfast"
    assert entries[0]["kcal"] == 500

    module_data = app_client.get("/api/modules/nutrition/data").json()
    assert module_data["primary_value"] == "500"


def test_nutrition_entries_require_auth(real_app_client):
    response = real_app_client.post("/api/nutrition/entries", json={"name": "Breakfast", "kcal": 500})
    assert response.status_code == 401
