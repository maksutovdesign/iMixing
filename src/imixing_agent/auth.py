from __future__ import annotations

import base64
import hashlib
import hmac
import os


_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if "@" not in email or len(email) > 254 or email.startswith("@") or email.endswith("@"):
        raise ValueError("Enter a valid email address.")
    return email


def validate_password(value: str) -> str:
    if len(value) < 10:
        raise ValueError("Password must contain at least 10 characters.")
    if len(value) > 256:
        raise ValueError("Password is too long.")
    return value


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return "$".join(
        ("scrypt", str(_SCRYPT_N), str(_SCRYPT_R), str(_SCRYPT_P), _encode(salt), _encode(digest))
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$")
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, _decode(expected))


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
