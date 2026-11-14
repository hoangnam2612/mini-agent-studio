"""Mật khẩu, JWT HS256 và URL tải file có ký — chỉ dùng stdlib (hashlib/hmac).

Vì sao không dùng thư viện JWT: phạm vi chỉ cần HS256 + exp, viết 30 dòng
dễ audit hơn thêm một dependency. Không hỗ trợ alg khác → không có lỗi
"alg=none".
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from src.config import get_settings

_PBKDF2_ROUNDS = 120_000


class TokenError(Exception):
    pass


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ROUNDS).hex()
    return f"pbkdf2${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$", 2)
    except ValueError:
        return False
    return hmac.compare_digest(hash_password(password, salt).split("$", 2)[2], digest)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _sign(message: bytes) -> str:
    return _b64(hmac.new(get_settings().jwt_secret.encode(), message, hashlib.sha256).digest())


def create_token(user_id: int, role: str, ttl_minutes: int | None = None) -> str:
    ttl = ttl_minutes if ttl_minutes is not None else get_settings().jwt_ttl_minutes
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64(json.dumps({"sub": user_id, "role": role, "exp": int(time.time()) + ttl * 60}).encode())
    signing_input = f"{header}.{payload}".encode()
    return f"{header}.{payload}.{_sign(signing_input)}"


def decode_token(token: str) -> dict:
    try:
        header, payload, signature = token.split(".")
        alg = json.loads(_unb64(header)).get("alg")
    except (ValueError, UnicodeDecodeError, AttributeError) as exc:
        raise TokenError("Token sai định dạng") from exc
    if alg != "HS256":
        raise TokenError("Thuật toán không được hỗ trợ")
    if not hmac.compare_digest(_sign(f"{header}.{payload}".encode()), signature):
        raise TokenError("Chữ ký không hợp lệ")
    claims = json.loads(_unb64(payload))
    if claims.get("exp", 0) < time.time():
        raise TokenError("Token đã hết hạn")
    return claims


def sign_file_url(evidence_id: int, ttl_seconds: int | None = None) -> str:
    """URL tải file có hạn (R15.1) — không lộ đường dẫn thật trên đĩa."""
    ttl = ttl_seconds if ttl_seconds is not None else get_settings().file_url_ttl_seconds
    exp = int(time.time()) + ttl
    sig = _sign(f"file:{evidence_id}:{exp}".encode())
    return f"/api/v1/files/{evidence_id}?exp={exp}&sig={sig}"


def verify_file_signature(evidence_id: int, exp: int, sig: str) -> bool:
    if exp < time.time():
        return False
    return hmac.compare_digest(_sign(f"file:{evidence_id}:{exp}".encode()), sig)
