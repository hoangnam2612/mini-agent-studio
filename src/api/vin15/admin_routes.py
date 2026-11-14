"""Vai trò tùy chọn Quản trị viên (UC-50, UC-53). Tắt bằng ENABLE_ADMIN_ROLE=false.

Khi tắt: mọi endpoint trả 404 — cấu hình lấy từ config/cohort.yaml + seed.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.api.vin15.auth_routes import current_cohort
from src.api.vin15.serializers import user_out
from src.config import get_settings
from src.core import audit
from src.core.auth import actor_of, require_role
from src.core.security import hash_password
from src.db import get_db
from src.models.orm import Internship, Milestone, MilestoneTemplate, User

router = APIRouter(prefix="/admin", tags=["admin"])


def admin_enabled() -> None:
    if not get_settings().enable_admin_role:
        raise HTTPException(status_code=404, detail="Vai trò Quản trị viên không được bật")


class UserIn(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9_.]+$")
    password: str = Field(min_length=6, max_length=128)
    role: Literal["student", "lecturer"]
    full_name: str = Field(min_length=2, max_length=128)
    email: str = Field(default="", max_length=128)
    student_code: str | None = Field(default=None, max_length=32)
    program: str = Field(default="", max_length=128)
    is_coordinator: bool = False


class AssignIn(BaseModel):
    student_id: int
    lecturer_id: int


class TemplateIn(BaseModel):
    code: str = Field(min_length=2, max_length=32)
    name: str = Field(min_length=3, max_length=128)
    anchor: Literal["start", "mid", "end"]
    offset_days: int = Field(ge=-60, le=120)
    required_evidence: list[str] = []
    linked_to: Literal["outline"] | None = None
    citation: dict = {}


@router.get("/users", dependencies=[Depends(admin_enabled)])
def list_users(user: User = Depends(require_role("admin")), db: Session = Depends(get_db)) -> list[dict]:
    return [user_out(u) for u in db.scalars(select(User).order_by(User.role, User.username)).all()]


@router.post("/users", status_code=201, dependencies=[Depends(admin_enabled)])
def create_user(body: UserIn, user: User = Depends(require_role("admin")), db: Session = Depends(get_db)) -> dict:
    if db.scalar(select(User.id).where(User.username == body.username)):
        raise HTTPException(status_code=409, detail="Tên đăng nhập đã tồn tại")
    new = User(username=body.username, password_hash=hash_password(body.password), role=body.role,
               full_name=body.full_name, email=body.email, student_code=body.student_code,
               program=body.program, is_coordinator=body.is_coordinator and body.role == "lecturer")
    db.add(new)
    db.flush()
    audit.record(db, actor_of(user), "user", new.id, "created", after={"username": new.username, "role": new.role})
    db.commit()
    return user_out(new)


@router.post("/assign", dependencies=[Depends(admin_enabled)])
def assign(body: AssignIn, user: User = Depends(require_role("admin")), db: Session = Depends(get_db)) -> dict:
    student, lecturer = db.get(User, body.student_id), db.get(User, body.lecturer_id)
    if not student or student.role != "student" or not lecturer or lecturer.role != "lecturer":
        raise HTTPException(status_code=422, detail="Cần một sinh viên và một giảng viên hợp lệ")
    before = student.lecturer_id
    student.lecturer_id = lecturer.id
    # Hồ sơ chưa kết thúc chuyển theo GV mới; hồ sơ đã hoàn thành giữ lịch sử
    for i in db.scalars(select(Internship).where(Internship.student_id == student.id,
                                                 Internship.status.not_in(("completed", "rejected")))).all():
        i.lecturer_id = lecturer.id
    audit.record(db, actor_of(user), "user", student.id, "lecturer_assigned",
                 before={"lecturer_id": before}, after={"lecturer_id": lecturer.id})
    db.commit()
    return user_out(student)


@router.get("/cohort", dependencies=[Depends(admin_enabled)])
def get_cohort(user: User = Depends(require_role("admin")), db: Session = Depends(get_db)) -> dict:
    cohort = current_cohort(db)
    return {"id": cohort.id, "code": cohort.code, "name": cohort.name, "templates": [
        {"code": t.code, "name": t.name, "anchor": t.due_rule["anchor"], "offset_days": t.due_rule.get("offset_days", 0),
         "required_evidence": t.required_evidence, "linked_to": t.linked_to, "citation": t.citation}
        for t in cohort.templates
    ]}


@router.put("/cohort/templates", dependencies=[Depends(admin_enabled)])
def replace_templates(body: list[TemplateIn], user: User = Depends(require_role("admin")),
                      db: Session = Depends(get_db)) -> dict:
    """Áp dụng cho hồ sơ được duyệt SAU thời điểm đổi; mốc đã sinh giữ nguyên."""
    if len({t.code for t in body}) != len(body):
        raise HTTPException(status_code=422, detail="Mã mốc bị trùng")
    cohort = current_cohort(db)
    before = [t.code for t in cohort.templates]
    # Upsert theo mã: mốc đã sinh vẫn trỏ đúng mẫu; mẫu bị bỏ thì gỡ liên kết trước khi xóa
    # (mốc đã sinh giữ bản sao tên/hạn/minh chứng nên không mất dữ liệu).
    existing = {t.code: t for t in cohort.templates}
    templates = []
    for n, t in enumerate(body):
        tpl = existing.pop(t.code, None) or MilestoneTemplate(code=t.code)
        tpl.name, tpl.ordinal = t.name, n
        tpl.due_rule = {"anchor": t.anchor, "offset_days": t.offset_days}
        tpl.required_evidence, tpl.citation, tpl.linked_to = t.required_evidence, t.citation, t.linked_to
        templates.append(tpl)
    removed_ids = [t.id for t in existing.values()]
    if removed_ids:
        db.execute(update(Milestone).where(Milestone.template_id.in_(removed_ids)).values(template_id=None))
    cohort.templates = templates
    audit.record(db, actor_of(user), "cohort", cohort.id, "templates_replaced",
                 before={"codes": before}, after={"codes": [t.code for t in body]})
    db.commit()
    return get_cohort(user, db)
