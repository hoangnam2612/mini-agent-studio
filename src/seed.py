"""Seed dữ liệu demo tổng hợp (A1) — chạy khi DB trống, hoặc `python -m scripts.seed`.

Mọi chuyển trạng thái trong seed vẫn đi qua `transition()` với actor đúng vai
trò, nên audit trail của dữ liệu demo nhất quán với dữ liệu thật.
Mật khẩu mọi tài khoản demo: demo123. KHÔNG dùng dữ liệu SV thật.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

import yaml
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.core import audit
from src.core.audit import Actor
from src.core.security import hash_password
from src.models.orm import (
    Cohort,
    Company,
    Evidence,
    ExtensionRequest,
    Internship,
    LogEntry,
    MilestoneTemplate,
    Outline,
    User,
    utcnow,
)
from src.services import lifecycle, monitor, policy_index, storage
from src.services.pii import Redactor
from src.services.reviewer import summarize_extension, summarize_outline
from src.workflow.rules import load_cohort_config
from src.workflow.state_machine import transition

logger = logging.getLogger("vin15.seed")

DEMO_PASSWORD = "demo123"
_LAST = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng"]
_MIDDLE = ["Văn", "Thị", "Minh", "Ngọc", "Gia", "Hải"]
_FIRST = ["An", "Bình", "Chi", "Dũng", "Giang", "Hà", "Khánh", "Linh", "My", "Nam", "Phúc", "Quân", "Trang", "Vy", "Yến"]
_DEMO_PDF = b"%PDF-1.4\n% VIN-15 demo evidence\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def human(user: User) -> Actor:
    return Actor(kind="human", user_id=user.id, role=user.role)


def parse_policy_file(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    if raw.startswith("---"):
        _, front, body = raw.split("---", 2)
        return yaml.safe_load(front), body
    return {}, raw


def seed_cohort(db: Session, today: date) -> Cohort:
    cfg = load_cohort_config()
    c = cfg["cohort"]
    cohort = Cohort(
        code=c["code"], name=c["name"],
        start_window=today + timedelta(days=c["start_window_offset_days"]),
        end_window=today + timedelta(days=c["end_window_offset_days"]),
        min_weeks=c["min_weeks"], hours_per_week=c["hours_per_week"],
        outcomes=cfg.get("outcomes", []), rules=cfg.get("rules", {}),
    )
    for n, m in enumerate(cfg.get("milestones", [])):
        cohort.templates.append(MilestoneTemplate(
            code=m["code"], name=m["name"], ordinal=n,
            due_rule={"anchor": m["anchor"], "offset_days": m.get("offset_days", 0)},
            required_evidence=m.get("required_evidence", []), citation=m.get("citation", {}),
            linked_to=m.get("linked_to"),
        ))
    db.add(cohort)
    db.flush()
    return cohort


def seed_users(db: Session) -> tuple[User, list[User], list[User]]:
    pw = hash_password(DEMO_PASSWORD)
    admin = User(username="admin", password_hash=pw, role="admin", full_name="Quản trị viên Đào tạo",
                 email="admin@demo.edu.vn")
    lecturers = [
        User(username=f"gv{n:02d}", password_hash=pw, role="lecturer", full_name=name,
             email=f"gv{n:02d}@demo.edu.vn", is_coordinator=(n == 1))
        for n, name in enumerate(["TS. Lê Minh Tâm", "ThS. Phạm Thu Hằng", "TS. Đỗ Quốc Huy"], start=1)
    ]
    db.add_all([admin, *lecturers])
    db.flush()
    students = []
    for n in range(1, 31):
        name = f"{_LAST[n % len(_LAST)]} {_MIDDLE[n % len(_MIDDLE)]} {_FIRST[n % len(_FIRST)]}"
        students.append(User(
            username=f"sv{n:02d}", password_hash=pw, role="student", full_name=name,
            email=f"sv{n:02d}@student.demo.edu.vn", phone=f"09{n:08d}", student_code=f"SV2026{n:03d}",
            program="Công nghệ thông tin" if n % 2 else "Quản trị kinh doanh",
            lecturer_id=lecturers[(n - 1) % len(lecturers)].id,
        ))
    db.add_all(students)
    db.flush()
    return admin, lecturers, students


def seed_policies(db: Session) -> None:
    folder = Path(get_settings().policy_seed_dir)
    for path in sorted(folder.glob("*.md")):
        meta, body = parse_policy_file(path)
        policy_index.ingest(
            db, code=meta["code"], title=meta["title"], text=body, issuer=meta.get("issuer", ""),
            effective_from=meta["effective_from"], supersedes_code=meta.get("supersedes"), filename=path.name,
        )


def _evidence(db: Session, internship: Internship, milestone, student: User, evidence_type: str) -> Evidence:
    stored = storage.save_file(f"{evidence_type}.pdf", _DEMO_PDF + evidence_type.encode())
    ev = Evidence(milestone_id=milestone.id, internship_id=internship.id, evidence_type=evidence_type,
                  filename=f"{evidence_type}.pdf", path=stored.path, mime=stored.mime, size=stored.size,
                  sha256=stored.sha256, uploaded_by=student.id)
    db.add(ev)
    db.flush()
    return ev


def _internship(db: Session, student: User, cohort: Cohort, company: Company, start: date, weeks: int) -> Internship:
    i = Internship(
        student_id=student.id, lecturer_id=student.lecturer_id, cohort_id=cohort.id, company_id=company.id,
        company_name=company.name, company_tax_code=company.tax_code, company_address=company.address,
        mentor_name="Ông Trần Quốc Bảo", mentor_email="bao.tq@demo-company.vn", mentor_phone="0912345678",
        position="Thực tập sinh phát triển phần mềm",
        job_description="Phát triển và kiểm thử API cho hệ thống nội bộ, tham gia họp nhóm Scrum hằng tuần.",
        start_date=start, end_date=start + timedelta(weeks=weeks), mode="full_time",
    )
    db.add(i)
    db.flush()
    audit.record(db, human(student), "internship", i.id, "created")
    return i


def _approve(db: Session, i: Internship, student: User, lecturer: User) -> None:
    transition(db, "internship", i, "submitted", human(student))
    transition(db, "internship", i, "approved", human(lecturer))
    db.flush()
    db.refresh(i)
    lifecycle.generate_milestones(i)
    db.flush()


def _complete_milestone(db: Session, i: Internship, code: str, student: User, lecturer: User) -> None:
    m = next(m for m in i.milestones if m.code == code)
    for t in m.required_evidence:
        _evidence(db, i, m, student, t)
    transition(db, "milestone", m, "submitted", human(student))
    m.submitted_at = utcnow()
    transition(db, "milestone", m, "accepted", human(lecturer))


def _logs(db: Session, i: Internship, weeks: int, hours: float) -> None:
    for w in range(1, weeks + 1):
        db.add(LogEntry(internship_id=i.id, week_no=w, hours=hours,
                        content=f"Tuần {w}: phân tích yêu cầu, viết API và kiểm thử; họp nhóm và báo cáo tiến độ.",
                        difficulties="Làm quen quy trình review code của công ty."))


def seed_demo(db: Session, today: date | None = None) -> bool:
    """Trả True nếu đã seed; False nếu DB đã có dữ liệu."""
    if db.scalar(select(func.count(User.id))):
        return False
    today = today or date.today()
    cohort = seed_cohort(db, today)
    _, lecturers, students = seed_users(db)
    seed_policies(db)
    companies = [
        Company(tax_code="0101234567", name="Công ty TNHH Giải pháp Phần mềm Sao Mai",
                address="12 Duy Tân, Cầu Giấy, Hà Nội"),
        Company(tax_code="0309876543", name="Công ty Cổ phần Dữ liệu Phương Nam",
                address="45 Nguyễn Thị Minh Khai, Quận 1, TP.HCM"),
        Company(tax_code="0401122334", name="Công ty TNHH Thương mại Hải Âu", address="8 Bạch Đằng, Đà Nẵng"),
    ]
    db.add_all(companies)
    db.flush()
    lect = {lec.id: lec for lec in lecturers}

    # sv02 — đã nộp, chờ GV duyệt hồ sơ
    sv = students[1]
    i = _internship(db, sv, cohort, companies[1], today + timedelta(days=10), 10)
    transition(db, "internship", i, "submitted", human(sv))

    # sv03 — đang thực tập 30 ngày, đề cương chờ duyệt, nhật ký thiếu giờ
    sv = students[2]
    i = _internship(db, sv, cohort, companies[0], today - timedelta(days=30), 10)
    _approve(db, i, sv, lect[sv.lecturer_id])
    _complete_milestone(db, i, "tiep_nhan", sv, lect[sv.lecturer_id])
    outline = Outline(internship_id=i.id, content=(
        "Mục tiêu: xây dựng module báo cáo cho hệ thống nội bộ. Nhiệm vụ: phân tích yêu cầu, thiết kế cơ sở dữ liệu, "
        "phát triển API. Kế hoạch: tuần 1–2 tìm hiểu; tuần 3–6 phát triển; tuần 7–10 kiểm thử và viết báo cáo."
    ))
    db.add(outline)
    db.flush()
    audit.record(db, human(sv), "outline", outline.id, "submitted")
    lifecycle.on_outline_submitted(db, i, human(sv))
    outline.ai_summary = summarize_outline(outline.content, cohort, Redactor())
    _logs(db, i, 4, 18)

    # sv04 — đang thực tập 20 ngày, quá hạn giấy tiếp nhận, đã xin gia hạn
    sv = students[3]
    i = _internship(db, sv, cohort, companies[2], today - timedelta(days=20), 9)
    _approve(db, i, sv, lect[sv.lecturer_id])
    _logs(db, i, 2, 34)
    db.flush()
    lifecycle.daily_status_job(db, today)
    m = next(m for m in i.milestones if m.code == "tiep_nhan")
    ext = ExtensionRequest(milestone_id=m.id, requested_by=sv.id, previous_due_date=m.due_date,
                           requested_due_date=today + timedelta(days=5),
                           reason="Doanh nghiệp chưa kịp đóng dấu giấy xác nhận do người hướng dẫn đi công tác.")
    db.add(ext)
    db.flush()
    db.refresh(ext)
    audit.record(db, human(sv), "extension", ext.id, "created")
    ext.ai_summary = summarize_extension(db, ext, Redactor(), today)

    # sv05 — đang thực tập 50 ngày, mọi thứ đúng hạn
    sv = students[4]
    i = _internship(db, sv, cohort, companies[0], today - timedelta(days=50), 12)
    _approve(db, i, sv, lect[sv.lecturer_id])
    _complete_milestone(db, i, "tiep_nhan", sv, lect[sv.lecturer_id])
    _complete_milestone(db, i, "giua_ky", sv, lect[sv.lecturer_id])
    outline = Outline(internship_id=i.id, content=(
        "Mục tiêu: vận dụng kiến thức để phát triển ứng dụng. Làm việc nhóm, tuân thủ quy trình bảo mật, "
        "viết báo cáo hằng tuần."
    ))
    db.add(outline)
    db.flush()
    lifecycle.on_outline_submitted(db, i, human(sv))
    transition(db, "outline", outline, "approved", human(lect[sv.lecturer_id]))
    lifecycle.on_outline_decided(db, i, "approved", human(lect[sv.lecturer_id]), "")
    _logs(db, i, 7, 36)

    # sv06 — hồ sơ bị yêu cầu chỉnh sửa
    sv = students[5]
    i = _internship(db, sv, cohort, companies[1], today + timedelta(days=5), 6)
    transition(db, "internship", i, "submitted", human(sv))
    transition(db, "internship", i, "revision_requested", human(lect[sv.lecturer_id]),
               "Thời lượng 6 tuần chưa đạt tối thiểu 8 tuần theo Điều 5 Khoản 2 QĐ-TT/2026.")
    i.decision_reason = "Thời lượng 6 tuần chưa đạt tối thiểu 8 tuần theo Điều 5 Khoản 2 QĐ-TT/2026."

    db.flush()
    monitor.run_all(db, today)  # commit bên trong
    logger.info("Seeded demo data")
    return True
