from __future__ import annotations

import base64
import hashlib
import hmac
import os
import subprocess
import tempfile
import time

from typing import Any


def _load_bcrypt() -> Any | None:
    try:
        import bcrypt  # type: ignore
    except ModuleNotFoundError:
        return None
    return bcrypt


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _hash_with_htpasswd(password: str) -> str:
    try:
        proc = subprocess.run(
            ['htpasswd', '-niB', 'user'],
            input=f'{password}\n',
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError('bcrypt backend is not available') from exc

    line = proc.stdout.strip()
    if ':' not in line:
        raise RuntimeError('failed to generate bcrypt hash')
    return line.split(':', 1)[1]


def _verify_with_htpasswd(password: str, password_hash: str) -> bool:
    path: str | None = None
    try:
        with tempfile.NamedTemporaryFile('w', delete=False) as fp:
            fp.write(f'user:{password_hash}\n')
            path = fp.name
        proc = subprocess.run(
            ['htpasswd', '-vb', path, 'user', password],
            capture_output=True,
            text=True,
        )
        return proc.returncode == 0
    except FileNotFoundError as exc:
        raise RuntimeError('bcrypt backend is not available') from exc
    finally:
        if path and os.path.exists(path):
            os.unlink(path)


def hash_password(password: str) -> str:
    bcrypt = _load_bcrypt()
    if bcrypt is not None:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    return _hash_with_htpasswd(password)


def verify_password(password: str, password_hash: str) -> bool:
    bcrypt = _load_bcrypt()
    if bcrypt is not None:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    return _verify_with_htpasswd(password, password_hash)


def create_session_token(user_id: int, secret: str, ttl_seconds: int) -> str:
    exp = int(time.time()) + ttl_seconds
    payload = f'{user_id}.{exp}'
    sig = hmac.new(secret.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).digest()
    sig_text = base64.urlsafe_b64encode(sig).decode('utf-8').rstrip('=')
    return f'{payload}.{sig_text}'


def parse_session_token(token: str, secret: str) -> int | None:
    try:
        user_id_text, exp_text, sig_text = token.split('.', 2)
        payload = f'{user_id_text}.{exp_text}'
        expected_sig = hmac.new(secret.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).digest()
        expected_sig_text = base64.urlsafe_b64encode(expected_sig).decode('utf-8').rstrip('=')
        if not hmac.compare_digest(sig_text, expected_sig_text):
            return None
        if int(exp_text) < int(time.time()):
            return None
        return int(user_id_text)
    except Exception:
        return None
