"""Tests for backend.main's /api/account/change-password and
/api/account/logout-all-sessions endpoints — per Phase 5's 'account
settings view' plan item.
"""


def _setup_and_login(app_client):
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


def test_change_password_with_correct_current_password_succeeds(app_client):
    _setup_and_login(app_client)

    response = app_client.post(
        "/api/account/change-password",
        json={"current_password": "correct-horse-battery-staple", "new_password": "new-even-better-password"},
    )
    assert response.status_code == 200

    # The old session is now invalid (change_password bumps session_epoch).
    modules_response = app_client.get("/api/modules")
    assert modules_response.status_code == 401

    # Logging in with the new password works.
    login_response = app_client.post(
        "/api/login", json={"email": "marcin@example.com", "password": "new-even-better-password"}
    )
    assert login_response.status_code == 200


def test_change_password_with_wrong_current_password_returns_400_and_keeps_session_valid(app_client):
    _setup_and_login(app_client)

    response = app_client.post(
        "/api/account/change-password",
        json={"current_password": "totally-wrong", "new_password": "new-even-better-password"},
    )
    assert response.status_code == 400

    # Session is still valid — a failed password check shouldn't log
    # the user out of their otherwise-valid session.
    modules_response = app_client.get("/api/modules")
    assert modules_response.status_code == 200


def test_change_password_requires_auth(app_client):
    response = app_client.post(
        "/api/account/change-password",
        json={"current_password": "x", "new_password": "y"},
    )
    assert response.status_code == 401


def test_logout_all_sessions_invalidates_current_session_too(app_client):
    _setup_and_login(app_client)

    response = app_client.post("/api/account/logout-all-sessions")
    assert response.status_code == 200

    modules_response = app_client.get("/api/modules")
    assert modules_response.status_code == 401


def test_logout_all_sessions_requires_auth(app_client):
    response = app_client.post("/api/account/logout-all-sessions")
    assert response.status_code == 401
