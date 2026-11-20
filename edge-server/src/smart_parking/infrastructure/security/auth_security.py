"""Password Hashing (bcrypt / PBKDF2) and JWT Token Manager for RBAC Authentication."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

try:
    import bcrypt as _bcrypt  # type: ignore
    _HAS_BCRYPT = True
except ImportError:
    _bcrypt = None  # type: ignore
    _HAS_BCRYPT = False

try:
    import jwt as _pyjwt  # type: ignore
    _HAS_PYJWT = True
except ImportError:
    _pyjwt = None  # type: ignore
    _HAS_PYJWT = False


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using bcrypt (or PBKDF2-SHA256 in bcrypt-style modular crypt format)."""
    if not plain_password:
        raise ValueError("Mật khẩu không được để trống.")
    if _HAS_BCRYPT and _bcrypt is not None:
        hashed = _bcrypt.hashpw(plain_password.encode("utf-8"), _bcrypt.gensalt(rounds=12))
        return hashed.decode("utf-8")

    # Modular crypt format compatible fallback: $pbkdf2-sha256$200000$<salt_b64>$<hash_b64>
    salt = os.urandom(16)
    iterations = 200_000
    dk = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
    salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=")
    dk_b64 = base64.urlsafe_b64encode(dk).decode("ascii").rstrip("=")
    return f"$pbkdf2-sha256${iterations}${salt_b64}${dk_b64}"


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored password_hash."""
    if not plain_password or not password_hash:
        return False
    if password_hash.startswith(("$2a$", "$2b$", "$2y$")):
        if _HAS_BCRYPT and _bcrypt is not None:
            try:
                return bool(
                    _bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
                )
            except Exception:
                return False
        return False

    if password_hash.startswith("$pbkdf2-sha256$"):
        try:
            parts = password_hash.split("$")
            iterations = int(parts[2])
            salt_b64 = parts[3]
            dk_b64 = parts[4]
            salt = base64.urlsafe_b64decode(salt_b64 + "=" * (-len(salt_b64) % 4))
            expected_dk = base64.urlsafe_b64decode(dk_b64 + "=" * (-len(dk_b64) % 4))
            computed = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
            return hmac.compare_digest(computed, expected_dk)
        except Exception:
            return False

    return False


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def create_access_token(
    user_id: int,
    username: str,
    role: str,
    secret_key: str,
    expire_hours: int = 12,
    algorithm: str = "HS256",
) -> str:
    """Issue a signed JWT access token for a user session."""
    now_ts = int(time.time())
    exp_ts = now_ts + int(expire_hours * 3600)
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "user_id": int(user_id),
        "username": username,
        "role": role,
        "iat": now_ts,
        "exp": exp_ts,
    }
    if _HAS_PYJWT and _pyjwt is not None:
        token = _pyjwt.encode(payload, secret_key, algorithm=algorithm)
        return token if isinstance(token, str) else token.decode("utf-8")

    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    sig = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url_encode(sig)}"


def decode_access_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256",
) -> Dict[str, Any]:
    """Verify and decode a JWT access token. Raises ValueError if invalid or expired."""
    if not token:
        raise ValueError("Token xác thực trống.")
    if _HAS_PYJWT and _pyjwt is not None:
        try:
            decoded = _pyjwt.decode(token, secret_key, algorithms=[algorithm])
            return dict(decoded)
        except Exception as exc:
            raise ValueError(f"Token không hợp lệ hoặc đã hết hạn: {exc}") from exc

    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Định dạng JWT không hợp lệ.")
    header_b64, payload_b64, sig_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    actual_sig = _b64url_decode(sig_b64)
    if not hmac.compare_digest(actual_sig, expected_sig):
        raise ValueError("Chữ ký JWT không hợp lệ.")
    payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    now_ts = int(time.time())
    if int(payload.get("exp", 0)) < now_ts:
        raise ValueError("Token đã hết hạn.")
    return dict(payload)
