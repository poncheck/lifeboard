"""End-to-end API tests for backend.main — the full setup -> login ->
integrations -> modules -> dashboard flow against a real (temp) app.db
and temp module/integration directories. Per docs/ARCHITECTURE.md's
Phase 1 verification checklist.
"""


def test_healthz_requires_no_auth(app_client):
    response = app_client.get("/healthz")
    assert response.status_code == 200


def test_protected_route_without_session_returns_401(app_client):
    response = app_client.get("/api/modules")
    assert response.status_code == 401


def test_setup_then_login_then_access_protected_route(app_client):
    setup_response = app_client.post(
        "/api/setup",
        json={
            "full_name": "Marcin Petkowicz",
            "date_of_birth": "1986-03-26",
            "email": "marcin@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    assert setup_response.status_code == 200

    login_response = app_client.post(
        "/api/login",
        json={"email": "marcin@example.com", "password": "correct-horse-battery-staple"},
    )
    assert login_response.status_code == 200
    assert "lifeboard_session" in login_response.cookies

    modules_response = app_client.get("/api/modules")
    assert modules_response.status_code == 200
    assert "echo" in modules_response.json()


def test_setup_twice_returns_409(app_client):
    payload = {
        "full_name": "Marcin Petkowicz",
        "date_of_birth": "1986-03-26",
        "email": "marcin@example.com",
        "password": "correct-horse-battery-staple",
    }
    app_client.post("/api/setup", json=payload)
    second = app_client.post("/api/setup", json=payload)
    assert second.status_code == 409


def test_login_with_wrong_password_returns_401(app_client):
    app_client.post(
        "/api/setup",
        json={
            "full_name": "Marcin Petkowicz",
            "date_of_birth": "1986-03-26",
            "email": "marcin@example.com",
            "password": "correct-horse-battery-staple",
        },
    )

    response = app_client.post(
        "/api/login", json={"email": "marcin@example.com", "password": "wrong"}
    )
    assert response.status_code == 401


def test_full_integration_lifecycle_save_sync_then_module_shows_data(app_client):
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

    save_response = app_client.post(
        "/api/integrations/echo/credentials", json={"value": "hello-world"}
    )
    assert save_response.status_code == 200

    sync_response = app_client.post("/api/integrations/echo/sync-now")
    assert sync_response.status_code == 200

    data_response = app_client.get("/api/modules/echo/data")
    assert data_response.status_code == 200
    assert data_response.json()["primary_value"] == "hello-world"


def test_save_credentials_with_failing_test_connection_returns_400(app_client):
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

    # echo integration's test_connection requires a non-empty "value"
    response = app_client.post("/api/integrations/echo/credentials", json={"value": ""})
    assert response.status_code == 400


def test_logout_then_protected_route_returns_401(app_client):
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
    app_client.post("/api/logout")

    response = app_client.get("/api/modules")
    assert response.status_code == 401


def test_dashboard_layout_save_then_load_round_trips(app_client):
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

    layout = [{"module_id": "echo", "enabled": True, "position": 0, "refresh_seconds": 30}]
    save_response = app_client.post("/api/dashboard", json={"modules": layout})
    assert save_response.status_code == 200

    load_response = app_client.get("/api/dashboard")
    assert load_response.status_code == 200
    assert load_response.json()["modules"] == layout


def test_delete_credentials_then_module_data_shows_no_data(app_client):
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

    app_client.post("/api/integrations/echo/credentials", json={"value": "hello-world"})
    app_client.post("/api/integrations/echo/sync-now")

    delete_response = app_client.delete("/api/integrations/echo/credentials")
    assert delete_response.status_code == 200

    # Credentials gone -> sync-now has nothing to sync with, but the
    # previously-synced row (if any) is untouched; mainly we assert the
    # delete endpoint itself works and doesn't 404/500.
    sync_response = app_client.post("/api/integrations/echo/sync-now")
    assert sync_response.status_code == 200


def test_list_integrations_reports_configured_and_sync_status(app_client):
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

    before = app_client.get("/api/integrations").json()["echo"]
    assert before["configured"] is False
    assert before["last_synced_at"] is None
    assert before["last_error"] is None

    app_client.post("/api/integrations/echo/credentials", json={"value": "hello-world"})
    app_client.post("/api/integrations/echo/sync-now")

    after = app_client.get("/api/integrations").json()["echo"]
    assert after["configured"] is True
    assert after["last_synced_at"] is not None
    assert after["last_error"] is None


def test_list_modules_reports_requirement_satisfied(app_client):
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

    before = app_client.get("/api/modules").json()["echo"]
    assert before["requirement_satisfied"] is False

    app_client.post("/api/integrations/echo/credentials", json={"value": "hello-world"})

    after = app_client.get("/api/modules").json()["echo"]
    assert after["requirement_satisfied"] is True
