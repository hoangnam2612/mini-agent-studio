"""Đăng nhập, hồ sơ người dùng, cấu hình đợt (R1, R4.1)."""

from __future__ import annotations

from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.vin15.serializers import user_out
from src.config import get_settings
from src.core import audit, oidc, ratelimit
from src.core.audit import Actor
from src.core.auth import actor_of, can_manage_policies, current_user
from src.core.oidc import OIDCError, oidc_enabled
from src.core.security import create_token, verify_password
from src.db import get_db
from src.models.orm import Cohort, User
from src.workflow.rules import load_cohort_config

router = APIRouter(tags=["auth"])


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


@router.post("/auth/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)) -> dict:
    username = body.username.strip().lower()
    try:
        ratelimit.check_login_allowed(username, request.client.host if request.client else "unknown")
    except HTTPException:
        audit.record(db, Actor(kind="human", role="anonymous"), "auth", None, "login_throttled", reason=username[:64])
        db.commit()
        raise
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(body.password, user.password_hash):
        ratelimit.record_login_failure(username)
        audit.record(db, Actor(kind="human", role="anonymous"), "auth", None, "login_failed", reason=username[:64])
        db.commit()
        raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu")
    ratelimit.record_login_success(username)
    if user.role == "admin" and not get_settings().enable_admin_role:
        raise HTTPException(status_code=403, detail="Vai trò Quản trị viên đang tắt")
    return {"token": create_token(user.id, user.role), "user": user_out(user)}


@router.get("/auth/oidc/config")
def oidc_config() -> dict:
    return {"enabled": oidc_enabled()}


@router.get("/auth/oidc/login")
async def oidc_login() -> RedirectResponse:
    if not oidc_enabled():
        raise HTTPException(status_code=404, detail="SSO chưa được cấu hình")
    try:
        return RedirectResponse(await oidc.authorize_url(), status_code=302)
    except (OIDCError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=502, detail=f"Không kết nối được IdP: {exc}") from exc


@router.get("/auth/oidc/callback")
async def oidc_callback(code: str = "", state: str = "", error: str = "", db: Session = Depends(get_db)) -> RedirectResponse:
    """Thành công → chuyển về SPA với token trong fragment (fragment không gửi lên server/log)."""
    def fail(message: str) -> RedirectResponse:
        audit.record(db, Actor(kind="human", role="anonymous"), "auth", None, "sso_failed", reason=message[:200])
        db.commit()
        return RedirectResponse("/#/sso-error/" + quote(message), status_code=302)

    if not oidc_enabled():
        raise HTTPException(status_code=404, detail="SSO chưa được cấu hình")
    if error or not code:
        return fail(error or "Thiếu mã đăng nhập")
    try:
        oidc.check_state(state)
        info = await oidc.fetch_userinfo(code)
    except (OIDCError, httpx.HTTPError) as exc:
        return fail(str(exc))
    email = (info.get("email") or "").strip().lower()
    username = (info.get("preferred_username") or "").strip().lower()
    user = None
    if email and info.get("email_verified", True):
        user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is None and username:
        user = db.scalar(select(User).where(User.username == username))
    if user is None:
        return fail("Tài khoản SSO chưa được cấp quyền trong hệ thống thực tập")
    if user.role == "admin" and not get_settings().enable_admin_role:
        return fail("Vai trò Quản trị viên đang tắt")
    audit.record(db, actor_of(user), "auth", user.id, "sso_login", reason=info.get("sub", "")[:120])
    db.commit()
    return RedirectResponse("/#/sso/" + create_token(user.id, user.role), status_code=302)


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return {
        **user_out(user),
        "can_manage_policies": can_manage_policies(user),
        "admin_enabled": get_settings().enable_admin_role,
    }


def current_cohort(db: Session) -> Cohort:
    cohort = db.scalar(select(Cohort).order_by(Cohort.id.desc()))
    if cohort is None:
        raise HTTPException(status_code=503, detail="Chưa cấu hình đợt thực tập")
    return cohort


@router.get("/config")
def config(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    cohort = current_cohort(db)
    return {
        "cohort": {
            "id": cohort.id, "code": cohort.code, "name": cohort.name,
            "start_window": cohort.start_window.isoformat(), "end_window": cohort.end_window.isoformat(),
            "min_weeks": cohort.min_weeks, "hours_per_week": cohort.hours_per_week, "outcomes": cohort.outcomes,
        },
        "milestone_templates": [
            {"code": t.code, "name": t.name, "due_rule": t.due_rule, "required_evidence": t.required_evidence}
            for t in cohort.templates
        ],
        "evidence_types": load_cohort_config().get("evidence_types", {}),
    }
