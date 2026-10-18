"""Tests for backend.core.auth — onboarding (once), login verification,
and signed session tokens. Per docs/ARCHITECTURE.md: single operator
account, bcrypt-hashed password in app.db, HTTP-only signed session
cookie.
"""
import pytest


@pytest.fixture
def auth_store(tmp_path):
    from backend.core.auth import AuthStore

    db_path = tmp_path / "app.db"
    return AuthStore(db_path, secret_key="test-secret-key-long-enough-for-signing")


def test_no_account_initially(auth_store):
    assert auth_store.has_account() is False


def test_create_account_succeeds_once(auth_store):
    auth_store.create_account(
        full_name="Marcin Petkowicz",
        date_of_birth="1986-03-26",
        email="marcin@example.com",
        password="correct-horse-battery-staple",
    )
    assert auth_store.has_account() is True


def test_create_account_twice_raises(auth_store):
    auth_store.create_account(
        full_name="Marcin Petkowicz",
        date_of_birth="1986-03-26",
        email="marcin@example.com",
        password="correct-horse-battery-staple",
    )

    with pytest.raises(auth_store.AlreadyOnboardedError):
        auth_store.create_account(
            full_name="Someone Else",
            date_of_birth="1990-01-01",
            email="other@example.com",
            password="another-password",
        )


def test_password_is_not_stored_in_plaintext(auth_store, tmp_path):
    import sqlite3

    auth_store.create_account(
        full_name="Marcin Petkowicz",
        date_of_birth="1986-03-26",
        email="marcin@example.com",
        password="correct-horse-battery-staple",
    )

    conn = sqlite3.connect(tmp_path / "app.db")
    row = conn.execute("SELECT password_hash FROM account").fetchone()
    assert "correct-horse-battery-staple" not in row[0]


def test_verify_login_with_correct_password_succeeds(auth_store):
    auth_store.create_account(
        full_name="Marcin Petkowicz",
        date_of_birth="1986-03-26",
        email="marcin@example.com",
        password="correct-horse-battery-staple",
    )

    assert auth_store.verify_login("marcin@example.com", "correct-horse-battery-staple") is True


def test_verify_login_with_wrong_password_fails(auth_store):
    auth_store.create_account(
        full_name="Marcin Petkowicz",
        date_of_birth="1986-03-26",
        email="marcin@example.com",
        password="correct-horse-battery-staple",
    )

    assert auth_store.verify_login("marcin@example.com", "wrong-password") is False


def test_verify_login_with_wrong_email_fails(auth_store):
    auth_store.create_account(
        full_name="Marcin Petkowicz",
        date_of_birth="1986-03-26",
        email="marcin@example.com",
        password="correct-horse-battery-staple",
    )

    assert auth_store.verify_login("nobody@example.com", "correct-horse-battery-staple") is False


def test_session_token_round_trips(auth_store):
    token = auth_store.create_session_token("marcin@example.com")
    email = auth_store.verify_session_token(token)
    assert email == "marcin@example.com"


def test_tampered_session_token_is_rejected(auth_store):
    token = auth_store.create_session_token("marcin@example.com")
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")

    assert auth_store.verify_session_token(tampered) is None


def test_session_token_signed_with_different_key_is_rejected(tmp_path):
    from backend.core.auth import AuthStore

    db_path = tmp_path / "app.db"
    store_a = AuthStore(db_path, secret_key="key-one-long-enough-for-signing")
    token = store_a.create_session_token("marcin@example.com")

    store_b = AuthStore(db_path, secret_key="key-two-long-enough-for-signing")
    assert store_b.verify_session_token(token) is None
