from __future__ import annotations

import base64
import hashlib
import json
from functools import lru_cache
from typing import Any

from app.core.config import get_settings


def _derive_key32(raw_secret: str) -> bytes:
    return hashlib.sha256(raw_secret.encode('utf-8')).digest()


class _XorCipher:
    """
    Lightweight reversible obfuscation used only when `cryptography` isn't installed.
    This is not meant to be strong encryption.
    """

    _prefix = 'xor1:'

    def __init__(self, secret: str) -> None:
        self._key = _derive_key32(secret)

    def encrypt(self, data: bytes) -> bytes:
        x = bytes(b ^ self._key[i % len(self._key)] for i, b in enumerate(data))
        return (self._prefix + base64.urlsafe_b64encode(x).decode('utf-8')).encode('utf-8')

    def decrypt(self, token: bytes) -> bytes:
        text = token.decode('utf-8')
        if not text.startswith(self._prefix):
            raise RuntimeError('invalid token prefix')
        raw = base64.urlsafe_b64decode(text[len(self._prefix) :].encode('utf-8'))
        return bytes(b ^ self._key[i % len(self._key)] for i, b in enumerate(raw))


def _derive_fernet_key(raw_secret: str) -> bytes:
    # Fernet expects a 32-byte key, urlsafe base64 encoded.
    return base64.urlsafe_b64encode(_derive_key32(raw_secret))


@lru_cache
def _cipher():
    cfg = get_settings()
    if not getattr(cfg, 'data_sources_crypto_key', None) or str(cfg.data_sources_crypto_key).startswith('change-me-'):
        raise RuntimeError('DATA_SOURCES_CRYPTO_KEY is not configured')

    try:
        from cryptography.fernet import Fernet  # type: ignore

        return Fernet(_derive_fernet_key(str(cfg.data_sources_crypto_key)))
    except ModuleNotFoundError:
        return _XorCipher(str(cfg.data_sources_crypto_key))


def encrypt_json(obj: Any) -> str:
    data = json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    token: bytes = _cipher().encrypt(data)
    return token.decode('utf-8')


def decrypt_json(token: str) -> Any:
    data: bytes = _cipher().decrypt(token.encode('utf-8'))
    return json.loads(data.decode('utf-8'))

