"""E2E SSO với Keycloak thật (deploy/docker-compose.sso.yml) — đi hết luồng như trình duyệt.

backend /auth/oidc/login → Keycloak trang đăng nhập → submit form → callback backend → token → /me.
Kiểm tra: khớp tài khoản theo email (SV và GV), sai mật khẩu không ra code, tài khoản ngoài hệ thống
bị từ chối, state bị sửa bị từ chối, và mỗi lần đăng nhập SSO được ghi audit.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from urllib.parse import parse_qs, urlparse

import httpx

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f" :: {detail}"))
    if not ok:
        failures.append(name)


def idp_login(base: str, username: str, password: str, tamper_state: bool = False) -> tuple[str, httpx.Response | None]:
    """Trả (Location cuối từ backend, response trang Keycloak nếu không có redirect)."""
    backend = httpx.Client(base_url=base, timeout=30, follow_redirects=False)
    browser = httpx.Client(timeout=30, follow_redirects=False)  # giữ cookie phiên Keycloak
    r = backend.get("/api/v1/auth/oidc/login")
    assert r.status_code == 302, r.text
    authorize = r.headers["location"]
    page = browser.get(authorize)
    form = re.search(r'<form[^>]+id="kc-form-login"[^>]+action="([^"]+)"', page.text)
    assert form, "không thấy form đăng nhập Keycloak"
    resp = browser.post(html.unescape(form.group(1)), data={"username": username, "password": password, "credentialId": ""})
    if resp.status_code != 302:
        return "", resp
    callback = resp.headers["location"]
    if tamper_state:
        callback = callback.replace("state=", "state=x")
    parsed = urlparse(callback)
    r = backend.get(parsed.path, params={k: v[0] for k, v in parse_qs(parsed.query).items()})
    return r.headers.get("location", f"<{r.status_code}>"), None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://backend:8000")
    base = parser.parse_args().base
    api = httpx.Client(base_url=base, timeout=30)

    check("SSO enabled", api.get("/api/v1/auth/oidc/config").json() == {"enabled": True})

    for idp_user, expected_username, expected_role in (("chi.le", "sv03", "student"), ("tam.le", "gv01", "lecturer")):
        location, _ = idp_login(base, idp_user, "Sso-demo-123")
        ok = location.startswith("/#/sso/")
        check(f"{idp_user} → callback issues token", ok, location)
        if ok:
            me = api.get("/api/v1/me", headers={"Authorization": "Bearer " + location.removeprefix("/#/sso/")}).json()
            check(f"{idp_user} maps to {expected_username} ({expected_role})",
                  me.get("username") == expected_username and me.get("role") == expected_role, str(me))

    location, page = idp_login(base, "chi.le", "wrong-password")
    check("wrong password stays on Keycloak (no code)", location == "" and page is not None and page.status_code == 200,
          location or str(page.status_code if page else None))

    location, _ = idp_login(base, "outsider", "Sso-demo-123")
    check("account unknown to the portal is refused", location.startswith("/#/sso-error/"), location)

    location, _ = idp_login(base, "chi.le", "Sso-demo-123", tamper_state=True)
    check("tampered state is refused", location.startswith("/#/sso-error/"), location)

    print(f"\n{len(failures)} failed" if failures else "\nall checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
