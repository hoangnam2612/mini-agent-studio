"""Rule engine (R2.4, R10.2) và Monitor (R10, P4)."""

from __future__ import annotations

from datetime import date, timedelta

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select

from src.core.audit import Actor
from src.models.orm import Internship, LogEntry, RiskFlag
from src.services import monitor
from src.services.lifecycle import close_flag, daily_status_job
from src.workflow.rules import validate_internship
from tests.test_vin15.conftest import internship_of

TODAY = date.today()


def _open_flags(db, internship_id=None):
    stmt = select(func.count(RiskFlag.id)).where(RiskFlag.open_key.is_not(None))
    if internship_id:
        stmt = stmt.where(RiskFlag.internship_id == internship_id)
    return db.scalar(stmt)


def test_validation_reports_each_failed_rule_with_citation(db):
    i = internship_of(db, "sv06")  # 6 tuần
    results = {r.rule_id: r for r in validate_internship(i, i.cohort)}
    assert not results["min_weeks"].passed and "8 tuần" in results["min_weeks"].message
    assert results["min_weeks"].citation["path"] == "Điều 5 / Khoản 2"
    i.company_tax_code = ""
    i.start_date, i.end_date = i.end_date, i.start_date
    results = {r.rule_id: r for r in validate_internship(i, i.cohort)}
    assert not results["required_fields"].passed and "Mã số thuế" in results["required_fields"].message
    assert not results["end_after_start"].passed
    i.start_date = i.cohort.start_window - timedelta(days=5)
    i.end_date = i.start_date + timedelta(weeks=10)
    assert not {r.rule_id: r for r in validate_internship(i, i.cohort)}["within_window"].passed


def test_seeded_flags_match_scenarios(db):
    sv03, sv04, sv05 = (internship_of(db, u) for u in ("sv03", "sv04", "sv05"))
    types = lambda i: {f.flag_type for f in db.scalars(select(RiskFlag).where(  # noqa: E731
        RiskFlag.internship_id == i.id, RiskFlag.open_key.is_not(None)))}
    assert types(sv03) == {"low_hours"}
    assert "overdue" in types(sv04)
    assert types(sv05) == set()


def test_due_soon_and_missing_evidence(db):
    i = internship_of(db, "sv03")
    m = next(m for m in i.milestones if m.code == "giua_ky")
    m.due_date = TODAY + timedelta(days=2)
    created = monitor.run_for(db, i, TODAY)
    assert any(f.flag_type == "due_soon" and f.severity == "info" for f in created)
    m.status = "submitted"  # nộp nhưng chưa có minh chứng midterm_report
    created = monitor.run_for(db, i, TODAY)
    assert any(f.flag_type == "missing_evidence" for f in created)
    # due_soon không còn đúng (đã nộp) → tự đóng
    assert not db.scalar(select(RiskFlag).where(RiskFlag.internship_id == i.id, RiskFlag.flag_type == "due_soon",
                                                RiskFlag.open_key.is_not(None)))


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(offset=st.integers(-30, 30), hours=st.floats(0, 40), runs=st.integers(2, 4))
def test_p4_monitor_is_idempotent(db, offset, hours, runs):
    i = internship_of(db, "sv03")
    i.milestones[2].due_date = TODAY + timedelta(days=offset)
    for log in i.logs:
        log.hours = hours
    monitor.run_for(db, i, TODAY)
    db.flush()
    first = _open_flags(db, i.id)
    for _ in range(runs):
        assert monitor.run_for(db, i, TODAY) == []
        db.flush()
    assert _open_flags(db, i.id) == first
    db.rollback()


def test_monitor_never_changes_internship_status(db):
    before = {i.id: i.status for i in db.scalars(select(Internship))}
    monitor.run_all(db, TODAY + timedelta(days=200))
    after = {i.id: i.status for i in db.scalars(select(Internship))}
    # chỉ job hệ thống approved→in_progress được phép đổi; monitor không đụng hồ sơ đã kết thúc/chờ duyệt
    for iid, status in before.items():
        assert after[iid] == status or (status == "approved" and after[iid] == "in_progress")


def test_dismissed_flag_is_not_recreated_for_7_days(db):
    i = internship_of(db, "sv03")
    flag = db.scalar(select(RiskFlag).where(RiskFlag.internship_id == i.id, RiskFlag.flag_type == "low_hours"))
    close_flag(db, flag, "dismissed", Actor("human", i.lecturer_id, "lecturer"), "SV làm bù cuối tuần")
    db.flush()
    assert monitor.run_for(db, i, TODAY) == []
    assert any(f.flag_type == "low_hours" for f in monitor.run_for(db, i, TODAY + timedelta(days=8)))


def test_low_hours_respects_part_time(db):
    i = internship_of(db, "sv03")
    i.mode = "part_time"
    for log in i.logs:
        log.hours = 14  # 4 tuần × 14 = 56 ≥ 4 × 16 × 0.8 = 51.2
    db.add(LogEntry(internship_id=i.id, week_no=9, content="bù", hours=0))
    db.flush()
    db.refresh(i)
    monitor.run_for(db, i, TODAY)
    assert not db.scalar(select(RiskFlag).where(RiskFlag.internship_id == i.id, RiskFlag.flag_type == "low_hours",
                                                RiskFlag.open_key.is_not(None)))


def test_daily_job_marks_overdue_and_starts_internships(db):
    i = internship_of(db, "sv05")
    m = next(m for m in i.milestones if m.status == "pending")
    result = daily_status_job(db, m.due_date + timedelta(days=1))
    assert result["overdue"] >= 1 and m.status == "overdue"
