"""Single-operator account, onboarding, and signed session tokens.

Per docs/ARCHITECTURE.md: one account, set up once on first boot
(full name, date of birth, email, password). Password stored as a
bcrypt hash. Sessions are signed tokens (itsdangerous) carried in an
HTTP-only cookie by the API layer — this module only creates/verifies
the token string, it doesn't touch cookies/HTTP directly.
"""
import sqlite3
from pathlib import Path

import bcrypt
from itsdangerous import BadSignature, URLSafeTimedSerializer

_SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 30  # 30 days, matches "remember me" intent


class AuthStore:
    class AlreadyOnboardedError(Exception):
        """Raised when create_account() is called but an account already
        exists. Onboarding is a one-time flow."""

    def __init__(self, db_path: Path, secret_key: str):
        if not secret_key:
            raise ValueError("secret_key is required for signing session tokens.")
        self._db_path = Path(db_path)
        self._serializer = URLSafeTimedSerializer(secret_key, salt="lifeboard-session")
        self._init_db()

    def _init_db(self) -> None:
        conn = self._connect()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS account (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                full_name TEXT NOT NULL,
                date_of_birth TEXT NOT NULL,
                email TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                session_epoch INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        # Pre-Phase-5 databases won't have this column yet — add it
        # without disturbing existing rows (defaults them to epoch 1,
        # so old sessions keep working until the first "log out all
        # sessions" click).
        existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(account)")}
        if "session_epoch" not in existing_columns:
            conn.execute("ALTER TABLE account ADD COLUMN session_epoch INTEGER NOT NULL DEFAULT 1")
        conn.commit()
        conn.close()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def has_account(self) -> bool:
        conn = self._connect()
        row = conn.execute("SELECT 1 FROM account WHERE id = 1").fetchone()
        conn.close()
        return row is not None

    def create_account(
        self, full_name: str, date_of_birth: str, email: str, password: str
    ) -> None:
        if self.has_account():
            raise self.AlreadyOnboardedError("An account already exists.")

        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        conn = self._connect()
        conn.execute(
            "INSERT INTO account (id, full_name, date_of_birth, email, password_hash) "
            "VALUES (1, ?, ?, ?, ?)",
            (full_name, date_of_birth, email, password_hash),
        )
        conn.commit()
        conn.close()

    def verify_login(self, email: str, password: str) -> bool:
        conn = self._connect()
        row = conn.execute(
            "SELECT email, password_hash FROM account WHERE id = 1"
        ).fetchone()
        conn.close()

        if row is None:
            return False

        stored_email, password_hash = row
        if email != stored_email:
            return False

        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))

    def change_password(self, current_password: str, new_password: str) -> bool:
        """Verifies current_password against the stored hash, and if it
        matches, stores new_password's hash and bumps session_epoch —
        every existing session token (including the one making this
        request) is invalidated, forcing a fresh login with the new
        password. Returns False (no change made) if current_password
        is wrong."""
        conn = self._connect()
        row = conn.execute("SELECT email, password_hash FROM account WHERE id = 1").fetchone()
        if row is None:
            conn.close()
            return False

        email, password_hash = row
        if not bcrypt.checkpw(current_password.encode("utf-8"), password_hash.encode("utf-8")):
            conn.close()
            return False

        new_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        conn.execute(
            "UPDATE account SET password_hash = ?, session_epoch = session_epoch + 1 WHERE id = 1",
            (new_hash,),
        )
        conn.commit()
        conn.close()
        return True

    def logout_all_sessions(self) -> None:
        """Bumps session_epoch, invalidating every existing session
        token (including the caller's own) without touching the
        password. Safe to call with no account yet (no-op)."""
        conn = self._connect()
        conn.execute("UPDATE account SET session_epoch = session_epoch + 1 WHERE id = 1")
        conn.commit()
        conn.close()

    def _current_session_epoch(self) -> int | None:
        conn = self._connect()
        row = conn.execute("SELECT session_epoch FROM account WHERE id = 1").fetchone()
        conn.close()
        return row[0] if row else None

    def create_session_token(self, email: str) -> str:
        return self._serializer.dumps({"email": email, "session_epoch": self._current_session_epoch()})

    def verify_session_token(self, token: str) -> str | None:
        try:
            data = self._serializer.loads(token, max_age=_SESSION_MAX_AGE_SECONDS)
        except BadSignature:
            return None

        current_epoch = self._current_session_epoch()
        # A token signed before session_epoch existed (or before the
        # account exists at all) has no "session_epoch" key — treat
        # that as epoch 1, matching _init_db's default, so tokens
        # issued by a Phase-1-4 deployment keep working after
        # upgrading to Phase 5 without forcing every session to log
        # back in.
        token_epoch = data.get("session_epoch", 1)
        if current_epoch is not None and token_epoch != current_epoch:
            return None
        return data.get("email")
