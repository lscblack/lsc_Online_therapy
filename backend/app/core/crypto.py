"""AES-256-GCM field encryption. Blob layout: 12-byte nonce || ciphertext+tag.

ENCRYPTION_KEY format: base64 (urlsafe or standard) of exactly 32 random bytes.
Never log plaintext or the key.
"""
import base64
import binascii
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

NONCE_LEN = 12
KEY_LEN = 32
_TAG_LEN = 16


class EncryptionKeyError(RuntimeError):
    """ENCRYPTION_KEY missing or malformed."""


class DecryptionError(ValueError):
    """Blob is malformed, tampered with, or encrypted under another key."""


def _aesgcm() -> AESGCM:
    raw = get_settings().encryption_key.strip()
    if not raw:
        raise EncryptionKeyError("ENCRYPTION_KEY is not set; cannot encrypt/decrypt")
    try:
        padded = raw + "=" * (-len(raw) % 4)
        key = (base64.urlsafe_b64decode(padded) if ("-" in raw or "_" in raw)
               else base64.b64decode(padded, validate=True))
    except (binascii.Error, ValueError) as e:
        raise EncryptionKeyError("ENCRYPTION_KEY must be base64 of 32 bytes") from e
    if len(key) != KEY_LEN:
        raise EncryptionKeyError(
            f"ENCRYPTION_KEY must decode to {KEY_LEN} bytes (got {len(key)})")
    return AESGCM(key)


def encrypt(plaintext: str) -> bytes:
    aes = _aesgcm()
    nonce = os.urandom(NONCE_LEN)
    return nonce + aes.encrypt(nonce, plaintext.encode("utf-8"), None)


def decrypt(blob: bytes) -> str:
    aes = _aesgcm()
    blob = bytes(blob)
    if len(blob) < NONCE_LEN + _TAG_LEN:
        raise DecryptionError("ciphertext too short")
    try:
        return aes.decrypt(blob[:NONCE_LEN], blob[NONCE_LEN:], None).decode("utf-8")
    except (InvalidTag, UnicodeDecodeError) as e:
        raise DecryptionError("decryption failed (tampered or wrong key)") from e
