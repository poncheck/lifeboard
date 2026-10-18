"""Credential encryption for LifeBoard integrations.

Per docs/ARCHITECTURE.md: integration credentials (API keys, tokens) are
encrypted at rest using Fernet symmetric encryption, keyed by SECRET_KEY
(the one secret that lives in .env, never in the database).
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


class DecryptionError(Exception):
    """Raised when a value cannot be decrypted with the given key —
    e.g. the key changed, or the value was encrypted with a different
    key. Never silently returns garbage."""


class CredentialCipher:
    """Encrypts/decrypts integration credentials using a key derived
    from SECRET_KEY via SHA-256 (Fernet requires a 32-byte urlsafe-base64
    key; SECRET_KEY itself may be any length/format the user chooses)."""

    def __init__(self, secret_key: str | None):
        if not secret_key:
            raise ValueError(
                "SECRET_KEY is required to encrypt/decrypt credentials. "
                "Set it in .env (see .env.example)."
            )
        derived_key = hashlib.sha256(secret_key.encode("utf-8")).digest()
        fernet_key = base64.urlsafe_b64encode(derived_key)
        self._fernet = Fernet(fernet_key)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise DecryptionError(
                "Could not decrypt value — SECRET_KEY may have changed."
            ) from exc
