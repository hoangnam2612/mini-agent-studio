"""SSO/OIDC — authorization code flow cho confidential client (R1.2).

Luồng: /auth/oidc/login → IdP → /auth/oidc/callback?code&state → đổi code lấy access token
(có client_secret) → gọi userinfo → khớp tài khoản nội bộ theo email (hoặc username).
Vai trò lấy từ tài khoản nội bộ, không tin claim vai trò của IdP: nhà trường phân quyền
trong hệ thống này. Tài khoản chưa có trong hệ thống bị từ chối (không tự tạo).

`state` được ký HMAC + có hạn 10 phút nên không cần lưu phía server. Không dùng id_token
(xác thực chữ ký RS256 cần thêm thư viện crypto); userinfo được gọi trực tiếp tới IdP qua
TLS bằng access token vừa đổi, nên danh tính lấy từ chính IdP.
"""

from __future__ import annotations

import hmac
import json
import secrets
import time
from urllib.parse import urlencode

import httpx

from src.config import get_settings
from src.core.security import _b64, _sign, _unb64

_discovery_cache: dict[str, dict] = {}


class OIDCError(Exception):
    pass


def oidc_enabled() -> bool:
    s = get_settings()
    return bool(s.oidc_issuer and s.oidc_client_id and s.oidc_client_secret)


def http_client() -> httpx.AsyncClient:
    """Điểm thay thế cho test (MockTransport)."""
    return httpx.AsyncClient(timeout=10)


async def discovery() -> dict:
    issuer = get_settings().oidc_issuer.rstrip("/")
    if issuer not in _discovery_cache:
        async with http_client() as client:
            r = await client.get(f"{issuer}/.well-known/openid-configuration")
        if r.status_code != 200:
            raise OIDCError(f"Không đọc được cấu hình OIDC của {issuer} (HTTP {r.status_code})")
        _discovery_cache[issuer] = r.json()
    return _discovery_cache[issuer]


def make_state() -> str:
    payload = _b64(json.dumps({"n": secrets.token_urlsafe(12), "exp": int(time.time()) + 600}).encode())
    return f"{payload}.{_sign(('oidc:' + payload).encode())}"


def check_state(state: str) -> None:
    try:
        payload, sig = state.split(".")
        exp = json.loads(_unb64(payload))["exp"]
    except (ValueError, KeyError, UnicodeDecodeError) as exc:
        raise OIDCError("state không hợp lệ") from exc
    if not hmac.compare_digest(_sign(("oidc:" + payload).encode()), sig) or exp < time.time():
        raise OIDCError("state không hợp lệ hoặc đã hết hạn")


async def authorize_url() -> str:
    s = get_settings()
    meta = await discovery()
    query = {
        "response_type": "code", "client_id": s.oidc_client_id, "redirect_uri": s.oidc_redirect_uri,
        "scope": s.oidc_scopes, "state": make_state(),
    }
    return f"{meta['authorization_endpoint']}?{urlencode(query)}"


async def fetch_userinfo(code: str) -> dict:
    s = get_settings()
    meta = await discovery()
    async with http_client() as client:
        token = await client.post(meta["token_endpoint"], data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": s.oidc_redirect_uri,
            "client_id": s.oidc_client_id, "client_secret": s.oidc_client_secret,
        })
        token_data = token.json()
        if token.status_code != 200 or "access_token" not in token_data:
            raise OIDCError("IdP từ chối mã đăng nhập")
        if token_data.get("id_token"):
            await verify_id_token(token_data["id_token"], meta)
        info = await client.get(meta["userinfo_endpoint"],
                                headers={"Authorization": f"Bearer {token_data['access_token']}"})
    if info.status_code != 200:
        raise OIDCError("Không lấy được thông tin người dùng từ IdP")
    return info.json()


async def verify_id_token(id_token: str, metadata: dict) -> dict:
    """Verify an OIDC JWT against the provider JWKS before trusting it."""
    try:
        import jwt
        from cryptography.hazmat.primitives.asymmetric.rsa import RSAAlgorithm
    except ImportError as exc:
        raise OIDCError("Thiếu PyJWT/cryptography để xác thực id_token") from exc
    jwks_uri = metadata.get("jwks_uri")
    if not jwks_uri:
        raise OIDCError("IdP thiếu jwks_uri")
    async with http_client() as client:
        response = await client.get(jwks_uri)
    if response.status_code != 200:
        raise OIDCError("Không lấy được JWKS của IdP")
    header = jwt.get_unverified_header(id_token)
    key = next((item for item in response.json().get("keys", []) if item.get("kid") == header.get("kid")), None)
    if not key:
        raise OIDCError("Không tìm thấy khóa ký id_token")
    try:
        public_key = RSAAlgorithm.from_jwk(json.dumps(key))
        issuer = get_settings().oidc_issuer.rstrip("/")
        return jwt.decode(id_token, public_key, algorithms=["RS256"],
                          audience=get_settings().oidc_client_id, issuer=issuer)
    except Exception as exc:
        raise OIDCError("Chữ ký id_token không hợp lệ") from exc
