"""FastAPI dependencies: lấy Actor từ Bearer token, kiểm vai trò (R1)."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from src.config import get_settings
from src.core.audit import Actor, record_denied
from src.core.security import TokenError, decode_token
from src.db import get_db
from src.models.orm import User


def current_user(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> User:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    try:
        claims = decode_token(authorization.split(" ", 1)[1].strip())
    except TokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    user = db.get(User, claims["sub"])
    if user is None:
        raise HTTPException(status_code=401, detail="Tài khoản không tồn tại")
    if user.role == "admin" and not get_settings().enable_admin_role:
        raise HTTPException(status_code=403, detail="Vai trò Quản trị viên đang tắt")
    return user


def actor_of(user: User) -> Actor:
    return Actor(kind="human", user_id=user.id, role=user.role)


def require_role(*roles: str) -> Callable[..., User]:
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            record_denied(actor_of(user), "endpoint", None, f"role={user.role} cần {roles}")
            raise HTTPException(status_code=403, detail="Không có quyền với chức năng này")
        return user

    return dependency


def can_manage_policies(user: User) -> bool:
    """R9: QTV quản lý kho quy định; khi tắt QTV thì GV điều phối đảm nhận."""
    if get_settings().enable_admin_role:
        return user.role == "admin"
    return user.role == "lecturer" and user.is_coordinator
