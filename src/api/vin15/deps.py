"""Scoping ở tầng truy vấn (R1.3–1.5, P5): SV chỉ thấy mình, GV chỉ thấy SV được phân công.

Mọi endpoint lấy thực thể qua các hàm `load_*` này — không truy vấn thẳng theo id.
Truy cập trái phép → 403 + audit "access_denied" (ghi bằng session riêng).
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from src.core.audit import record_denied
from src.core.auth import actor_of
from src.models.orm import Evidence, ExtensionRequest, Internship, LogEntry, Milestone, Outline, RiskFlag, User


def can_access(user: User, internship: Internship) -> bool:
    if user.role == "student":
        return internship.student_id == user.id
    if user.role == "lecturer":
        return internship.lecturer_id == user.id
    return user.role == "admin"


def scoped_internships(user: User) -> Select:
    stmt = select(Internship)
    if user.role == "student":
        return stmt.where(Internship.student_id == user.id)
    if user.role == "lecturer":
        return stmt.where(Internship.lecturer_id == user.id)
    return stmt


def _guard(user: User, internship: Internship, entity: str, entity_id: int) -> None:
    if not can_access(user, internship):
        record_denied(actor_of(user), entity, entity_id, f"internship={internship.id}")
        raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập hồ sơ này")


def _get(db: Session, model, entity_id: int, label: str):
    obj = db.get(model, entity_id)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy {label}")
    return obj


def load_internship(db: Session, user: User, internship_id: int) -> Internship:
    i = _get(db, Internship, internship_id, "hồ sơ thực tập")
    _guard(user, i, "internship", i.id)
    return i


def load_milestone(db: Session, user: User, milestone_id: int) -> Milestone:
    m = _get(db, Milestone, milestone_id, "mốc")
    _guard(user, m.internship, "milestone", m.id)
    return m


def load_outline(db: Session, user: User, outline_id: int) -> Outline:
    o = _get(db, Outline, outline_id, "đề cương")
    _guard(user, o.internship, "outline", o.id)
    return o


def load_extension(db: Session, user: User, extension_id: int) -> ExtensionRequest:
    e = _get(db, ExtensionRequest, extension_id, "yêu cầu gia hạn")
    _guard(user, e.milestone.internship, "extension", e.id)
    return e


def load_log(db: Session, user: User, log_id: int) -> LogEntry:
    log = _get(db, LogEntry, log_id, "nhật ký")
    _guard(user, log.internship, "log_entry", log.id)
    return log


def load_evidence(db: Session, user: User, evidence_id: int) -> Evidence:
    ev = _get(db, Evidence, evidence_id, "minh chứng")
    _guard(user, db.get(Internship, ev.internship_id), "evidence", ev.id)
    return ev


def load_flag(db: Session, user: User, flag_id: int) -> RiskFlag:
    f = _get(db, RiskFlag, flag_id, "cờ rủi ro")
    _guard(user, f.internship, "risk_flag", f.id)
    return f
