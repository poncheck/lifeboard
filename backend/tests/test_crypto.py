"""Tests for backend.core.crypto — Fernet encryption keyed by SECRET_KEY.

Per docs/ARCHITECTURE.md: integration credentials are encrypted at rest.
A missing/invalid SECRET_KEY must fail loudly at boot, never silently
fall back to storing plaintext.
"""
import pytest


def test_round_trip_encrypt_decrypt_returns_original_value():
    from backend.core.crypto import CredentialCipher

    cipher = CredentialCipher(secret_key="a-test-secret-key-that-is-long-enough")
    plaintext = "super-secret-api-key-12345"

    encrypted = cipher.encrypt(plaintext)
    decrypted = cipher.decrypt(encrypted)

    assert decrypted == plaintext


def test_encrypted_value_does_not_contain_plaintext():
    from backend.core.crypto import CredentialCipher

    cipher = CredentialCipher(secret_key="a-test-secret-key-that-is-long-enough")
    plaintext = "super-secret-api-key-12345"

    encrypted = cipher.encrypt(plaintext)

    assert plaintext not in encrypted


def test_decrypt_with_wrong_key_raises_instead_of_returning_garbage():
    from backend.core.crypto import CredentialCipher, DecryptionError

    cipher_a = CredentialCipher(secret_key="key-one-that-is-long-enough-aaaa")
    cipher_b = CredentialCipher(secret_key="key-two-that-is-long-enough-bbbb")

    encrypted = cipher_a.encrypt("some-secret-value")

    with pytest.raises(DecryptionError):
        cipher_b.decrypt(encrypted)


def test_missing_secret_key_raises_at_construction():
    from backend.core.crypto import CredentialCipher

    with pytest.raises(ValueError, match="SECRET_KEY"):
        CredentialCipher(secret_key="")


def test_none_secret_key_raises_at_construction():
    from backend.core.crypto import CredentialCipher

    with pytest.raises(ValueError, match="SECRET_KEY"):
        CredentialCipher(secret_key=None)
