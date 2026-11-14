"""Cờ rủi ro, thông báo, chạy Monitor thủ công (R10)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.vin15.deps import load_flag, scoped_internships
from src.api.vin15.serializers import flag_out, notification_out
from src.core import audit
from src.core.auth import actor_of, can_manage_policies, current_user, require_role
from src.db import get_db
from src.models.orm import Internship, Notification, RiskFlag, User, utcnow
from src.services import monitor
from src.services.lifecycle import close_flag

router = APIRouter(tags=["monitor"])


class FlagActionIn(BaseModel):
    action: Literal["acknowledge", "resolve", "dismiss"]
    note: str = Field(default="", max_length=2000)


@router.get("/risk-flags")
def list_flags(status: Literal["open", "closed", "all"] = "open", user: User = Depends(current_user),
               db: Session = Depends(get_db)) -> list[dict]:
    ids = scoped_internships(user).with_only_columns(Internship.id)
    stmt = select(RiskFlag).where(RiskFlag.internship_id.in_(ids))
    if status == "open":
        stmt = stmt.where(RiskFlag.open_key.is_not(None))
    elif status == "closed":
        stmt = stmt.where(RiskFlag.open_key.is_(None))
    rank = {"critical": 0, "warning": 1, "info": 2}
    flags = sorted(db.scalars(stmt).all(), key=lambda f: (rank.get(f.severity, 3), f.created_at))
    return [flag_out(f) for f in flags]


@router.patch("/risk-flags/{flag_id}")
def act_on_flag(flag_id: int, body: FlagActionIn, user: User = Depends(require_role("lecturer")),
                db: Session = Depends(get_db)) -> dict:
    flag = load_flag(db, user, flag_id)
    if flag.open_key is None:
        raise HTTPException(status_code=409, detail="Cờ đã đóng")
    actor = actor_of(user)
    if body.action == "acknowledge":
        before = flag.status
        flag.status = "acknowledged"
        audit.record(db, actor, "risk_flag", flag.id, f"status:{before}->acknowledged", reason=body.note)
    elif body.action == "resolve":
        close_flag(db, flag, "resolved", actor, body.note or "GV đánh dấu đã xử lý")
    else:
        if not body.note.strip():
            raise HTTPException(status_code=422, detail="Bác bỏ cảnh báo cần ghi lý do")
        close_flag(db, flag, "dismissed", actor, body.note.strip())
    db.commit()
    return flag_out(flag)


@router.get("/notifications")
def list_notifications(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id)
                      .order_by(Notification.id.desc()).limit(50)).all()
    return [notification_out(n) for n in rows]


@router.post("/notifications/read-all")
def read_all(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    count = 0
    for n in db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))):
        n.read_at = utcnow()
        count += 1
    db.commit()
    return {"marked": count}


@router.post("/monitor/run")
def run_monitor(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Chạy Monitor ngay (demo/vận hành) — QTV, hoặc GV điều phối khi tắt QTV."""
    if not can_manage_policies(user):
        raise HTTPException(status_code=403, detail="Không có quyền chạy giám sát")
    audit.record(db, actor_of(user), "monitor", None, "manual_run")
    return monitor.run_all(db, date.today())
