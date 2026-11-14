"""Tác tử giám sát theo luật (R10, UC-100 → UC-105).

Chạy với Actor(kind="system"): không thể đi vào cạnh quyết định (P1).
Không tạo trùng cờ đang mở nhờ UNIQUE(open_key) + kiểm tra trước (P4).
Cờ không còn đúng điều kiện được đóng tự động — tránh nhắc việc đã xong.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.core import audit
from src.core.audit import Actor
from src.db import session_factory
from src.models.orm import Internship, RiskFlag
from src.services.lifecycle import close_flag, daily_status_job
from src.services.notifications import notify
from src.workflow.rules import evaluate_monitor

logger = logging.getLogger("vin15.monitor")

_SEVERITY_RANK = {"info": 0, "warning": 1, "critical": 2}


def open_key(internship_id: int, flag_type: str, milestone_id: int | None) -> str:
    return f"{internship_id}:{flag_type}:{milestone_id or 0}"


DISMISS_SUPPRESS_DAYS = 7


def _recently_dismissed(db: Session, internship_id: int, flag_type: str, milestone_id: int | None, today: date) -> bool:
    """GV đã bác bỏ cờ cùng loại trong 7 ngày → không tạo lại (tránh spam cảnh báo sai)."""
    since = datetime.combine(today - timedelta(days=DISMISS_SUPPRESS_DAYS), datetime.min.time())
    stmt = select(RiskFlag.id).where(
        RiskFlag.internship_id == internship_id,
        RiskFlag.flag_type == flag_type,
        RiskFlag.milestone_id.is_(None) if milestone_id is None else RiskFlag.milestone_id == milestone_id,
        RiskFlag.status == "dismissed",
        RiskFlag.closed_at >= since,
    )
    return db.scalar(stmt.limit(1)) is not None


def run_for(db: Session, internship: Internship, today: date) -> list[RiskFlag]:
    """Đánh giá 1 hồ sơ, upsert cờ. Trả về các cờ MỚI tạo."""
    if internship.status not in ("approved", "in_progress"):
        return []
    system = Actor.system()
    findings = evaluate_monitor(internship, today)
    wanted = {open_key(internship.id, f.rule_id, f.milestone_id): f for f in findings}
    existing = {
        flag.open_key: flag
        for flag in db.scalars(
            select(RiskFlag).where(RiskFlag.internship_id == internship.id, RiskFlag.open_key.is_not(None))
        ).all()
    }
    for key, flag in existing.items():
        if key not in wanted:
            close_flag(db, flag, "resolved", system, "Đóng tự động: điều kiện cảnh báo không còn")

    created: list[RiskFlag] = []
    for key, finding in wanted.items():
        if key in existing or _recently_dismissed(db, internship.id, finding.rule_id, finding.milestone_id, today):
            continue
        flag = RiskFlag(
            internship_id=internship.id, milestone_id=finding.milestone_id, flag_type=finding.rule_id,
            severity=finding.severity, reason=finding.message, evidence_refs=finding.evidence, open_key=key,
        )
        db.add(flag)
        db.flush()
        audit.record(db, system, "risk_flag", flag.id, "created", after={"type": flag.flag_type, "severity": flag.severity})
        notify(db, internship.student_id, "risk_flag", f"Nhắc việc: {finding.message}", link=f"#/internship/{internship.id}")
        if _SEVERITY_RANK[flag.severity] >= _SEVERITY_RANK["warning"]:
            notify(db, internship.lecturer_id, "risk_flag",
                   f"Cảnh báo SV {internship.student.full_name}: {finding.message}", link="#/flags")
        created.append(flag)
    return created


def run_all(db: Session, today: date | None = None) -> dict:
    today = today or date.today()
    status = daily_status_job(db, today)
    created = 0
    for internship in db.scalars(
        select(Internship).where(Internship.status.in_(("approved", "in_progress")))
    ).all():
        created += len(run_for(db, internship, today))
    db.commit()
    logger.info("monitor run: %s, flags created=%d", status, created)
    return {**status, "flags_created": created}


def run_for_event(db: Session, internship: Internship) -> None:
    """Gọi sau sự kiện (nộp nhật ký/minh chứng/đổi trạng thái) — R10.1."""
    run_for(db, internship, date.today())


async def scheduler_loop() -> None:
    """Chạy run_all mỗi ngày lúc MONITOR_HOUR (giờ máy chủ) và một lần khi khởi động."""
    settings = get_settings()
    while True:
        try:
            db = session_factory()()
            try:
                run_all(db)
            finally:
                db.close()
        except Exception as exc:  # job lỗi không được làm sập API
            logger.error("FAILED monitor run: %s", exc)
        now = datetime.now()
        next_run = now.replace(hour=settings.monitor_hour, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        await asyncio.sleep((next_run - now).total_seconds())
