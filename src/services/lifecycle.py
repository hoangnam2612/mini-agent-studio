"""Hệ quả nghiệp vụ quanh các chuyển trạng thái (R4, R12).

Mọi đổi trạng thái vẫn đi qua `transition()`; module này chỉ gom các bước
đi kèm: sinh mốc khi hồ sơ được duyệt, đồng bộ mốc gắn đề cương, đánh dấu
quá hạn, dời hạn khi gia hạn được duyệt (P8).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import audit
from src.core.audit import Actor
from src.models.orm import ExtensionRequest, Internship, Milestone, RiskFlag, utcnow
from src.services.notifications import notify
from src.workflow.rules import milestone_due_date
from src.workflow.state_machine import transition


def generate_milestones(internship: Internship) -> None:
    """R4.2 — sinh mốc cụ thể từ mẫu của đợt khi hồ sơ được duyệt."""
    if internship.milestones:
        return
    for tpl in internship.cohort.templates:
        internship.milestones.append(Milestone(
            template_id=tpl.id,
            code=tpl.code,
            name=tpl.name,
            ordinal=tpl.ordinal,
            due_date=milestone_due_date(
                tpl.due_rule["anchor"], tpl.due_rule.get("offset_days", 0), internship.start_date, internship.end_date
            ),
            required_evidence=list(tpl.required_evidence or []),
            citation=dict(tpl.citation or {}),
            linked_to=tpl.linked_to,
        ))


def outline_milestone(internship: Internship) -> Milestone | None:
    return next((m for m in internship.milestones if m.linked_to == "outline"), None)


def on_outline_submitted(db: Session, internship: Internship, actor: Actor) -> None:
    m = outline_milestone(internship)
    if m and m.status in ("pending", "overdue", "rejected"):
        transition(db, "milestone", m, "submitted", actor)
        m.submitted_at = utcnow()


def on_outline_decided(db: Session, internship: Internship, decision: str, actor: Actor, reason: str) -> None:
    m = outline_milestone(internship)
    if m and m.status == "submitted":
        transition(db, "milestone", m, "accepted" if decision == "approved" else "rejected", actor, reason)
        m.comment = reason
        if decision == "approved":
            maybe_complete(db, internship)


def maybe_complete(db: Session, internship: Internship) -> None:
    if internship.status == "in_progress" and internship.milestones and all(
        m.status == "accepted" for m in internship.milestones
    ):
        transition(db, "internship", internship, "completed", Actor.system())
        notify(db, internship.student_id, "completed", "Bạn đã hoàn thành mọi mốc thực tập")


def daily_status_job(db: Session, today: date) -> dict:
    """Job hằng ngày (UC-107): approved → in_progress; mốc quá hạn → overdue."""
    system = Actor.system()
    started = overdue = 0
    for i in db.scalars(select(Internship).where(Internship.status == "approved")).all():
        if i.start_date and i.start_date <= today:
            transition(db, "internship", i, "in_progress", system)
            started += 1
    stmt = (
        select(Milestone)
        .join(Internship)
        .where(Milestone.status.in_(("pending", "rejected")), Milestone.due_date < today,
               Internship.status.in_(("approved", "in_progress")))
    )
    for m in db.scalars(stmt).all():
        transition(db, "milestone", m, "overdue", system)
        overdue += 1
    return {"started": started, "overdue": overdue}


def apply_extension(db: Session, request: ExtensionRequest, actor: Actor) -> None:
    """R12.4 — dời hạn, gỡ overdue, đóng cờ quá hạn liên quan; cùng transaction với quyết định."""
    m = request.milestone
    before = m.due_date
    m.due_date = request.requested_due_date
    audit.record(
        db, actor, "milestone", m.id, "due_date_changed",
        before={"due_date": before.isoformat()}, after={"due_date": m.due_date.isoformat(), "extension_id": request.id},
        reason=f"Gia hạn #{request.id} đã duyệt",
    )
    if m.status == "overdue":
        transition(db, "milestone", m, "pending", actor, f"Gia hạn #{request.id}")
    flags = db.scalars(
        select(RiskFlag).where(RiskFlag.milestone_id == m.id, RiskFlag.flag_type.in_(("overdue", "due_soon")),
                               RiskFlag.open_key.is_not(None))
    ).all()
    for flag in flags:
        close_flag(db, flag, "resolved", actor, f"Đóng tự động: gia hạn #{request.id} đã duyệt")


def close_flag(db: Session, flag: RiskFlag, status: str, actor: Actor, note: str) -> None:
    before = flag.status
    flag.status = status
    flag.open_key = None
    flag.resolution_note = note
    flag.resolved_by = actor.user_id
    flag.closed_at = utcnow()
    audit.record(db, actor, "risk_flag", flag.id, f"status:{before}->{status}", reason=note)
