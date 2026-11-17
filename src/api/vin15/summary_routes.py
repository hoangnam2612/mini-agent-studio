"""Danh sách tổng hợp cho GV/QTV (R7): lọc, sắp xếp, tìm kiếm, phân trang, xuất CSV/XLSX.

Phạm vi theo người gọi (P5): GV chỉ thấy SV được phân công, QTV thấy tất cả, SV không có quyền.
File xuất chỉ chứa các cột của bảng — không có email/SĐT/mã số thuế (R7.3).
"""

from __future__ import annotations

import csv
import io
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.api.vin15.deps import scoped_internships
from src.core import audit
from src.core.auth import actor_of, require_role
from src.core.time import local_today
from src.db import get_db
from src.models.orm import Internship, RiskFlag, User

router = APIRouter(tags=["summary"])

_SEVERITY_RANK = {"critical": 3, "warning": 2, "info": 1}
_STATUS_VI = {
    "draft": "Nháp", "submitted": "Chờ duyệt", "revision_requested": "Cần chỉnh sửa", "approved": "Đã duyệt",
    "rejected": "Từ chối", "in_progress": "Đang thực tập", "completed": "Hoàn thành",
}
SortKey = Literal["student", "company", "status", "progress", "next_due", "risk"]
COLUMNS = [
    ("student_code", "Mã SV"), ("student_name", "Sinh viên"), ("program", "Ngành"), ("cohort", "Đợt"),
    ("lecturer", "GV phụ trách"), ("company", "Doanh nghiệp"), ("status_label", "Trạng thái"),
    ("progress_pct", "% mốc hoàn thành"), ("next_milestone", "Mốc kế tiếp"), ("next_due", "Hạn mốc kế tiếp"),
    ("open_flags", "Số cảnh báo mở"), ("max_severity", "Mức cao nhất"),
]


class Filters:
    def __init__(
        self,
        cohort_id: int | None = None,
        program: str | None = None,
        lecturer_id: int | None = None,
        status: str | None = None,
        risk: Literal["any", "none", "info", "warning", "critical"] | None = None,
        q: str | None = Query(default=None, max_length=100),
        sort: SortKey = "risk",
        order: Literal["asc", "desc"] = "desc",
    ):
        self.cohort_id, self.program, self.lecturer_id, self.status = cohort_id, program, lecturer_id, status
        self.risk, self.q, self.sort, self.order = risk, (q or "").strip().lower(), sort, order


def _row(i: Internship, flags: list[RiskFlag]) -> dict:
    ms = i.milestones
    done = sum(1 for m in ms if m.status == "accepted")
    upcoming = sorted((m for m in ms if m.status != "accepted"), key=lambda m: m.due_date)
    nxt = upcoming[0] if upcoming else None
    worst = max((f.severity for f in flags), key=lambda s: _SEVERITY_RANK[s], default=None)
    return {
        "id": i.id, "student_id": i.student_id, "student_code": i.student.student_code or "",
        "student_name": i.student.full_name, "program": i.student.program, "cohort": i.cohort.name,
        "cohort_id": i.cohort_id, "lecturer": i.lecturer.full_name if i.lecturer else "",
        "lecturer_id": i.lecturer_id, "company": i.company_name, "status": i.status,
        "status_label": _STATUS_VI.get(i.status, i.status),
        "progress_pct": round(100 * done / len(ms)) if ms else 0,
        "next_milestone": nxt.name if nxt else "", "next_due": nxt.due_date.isoformat() if nxt else "",
        "next_status": nxt.status if nxt else "", "open_flags": len(flags), "max_severity": worst or "",
    }


def build_rows(db: Session, user: User, f: Filters) -> list[dict]:
    stmt = scoped_internships(user).options(
        selectinload(Internship.student), selectinload(Internship.lecturer),
        selectinload(Internship.cohort), selectinload(Internship.milestones),
    )
    if f.cohort_id:
        stmt = stmt.where(Internship.cohort_id == f.cohort_id)
    if f.lecturer_id:
        stmt = stmt.where(Internship.lecturer_id == f.lecturer_id)
    if f.status:
        stmt = stmt.where(Internship.status == f.status)
    internships = db.scalars(stmt).all()
    flags: dict[int, list[RiskFlag]] = {}
    ids = [i.id for i in internships]
    if ids:
        for flag in db.scalars(select(RiskFlag).where(RiskFlag.internship_id.in_(ids), RiskFlag.open_key.is_not(None))):
            flags.setdefault(flag.internship_id, []).append(flag)
    rows = [_row(i, flags.get(i.id, [])) for i in internships]
    if f.program:
        rows = [r for r in rows if r["program"] == f.program]
    if f.risk == "any":
        rows = [r for r in rows if r["open_flags"]]
    elif f.risk == "none":
        rows = [r for r in rows if not r["open_flags"]]
    elif f.risk:
        rows = [r for r in rows if r["max_severity"] == f.risk]
    if f.q:
        rows = [r for r in rows if f.q in " ".join((r["student_name"], r["student_code"], r["company"])).lower()]
    key = {
        "student": lambda r: r["student_name"].lower(), "company": lambda r: r["company"].lower(),
        "status": lambda r: r["status"], "progress": lambda r: r["progress_pct"],
        "next_due": lambda r: r["next_due"] or "9999", "risk": lambda r: (_SEVERITY_RANK.get(r["max_severity"], 0), r["open_flags"]),
    }[f.sort]
    rows.sort(key=key, reverse=f.order == "desc")
    return rows


@router.get("/internships-summary")
def summary(
    f: Filters = Depends(),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    user: User = Depends(require_role("lecturer", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    rows = build_rows(db, user, f)
    facets = {
        "programs": sorted({r["program"] for r in rows if r["program"]}),
        "statuses": sorted({r["status"] for r in rows}),
    }
    start = (page - 1) * page_size
    return {"total": len(rows), "page": page, "page_size": page_size, "items": rows[start:start + page_size],
            "facets": facets, "today": local_today().isoformat()}


@router.get("/internships-summary/export")
def export(
    f: Filters = Depends(),
    format: Literal["csv", "xlsx"] = "csv",
    user: User = Depends(require_role("lecturer", "admin")),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    rows = build_rows(db, user, f)
    audit.record(db, actor_of(user), "internship", None, "exported", after={"format": format, "rows": len(rows)})
    db.commit()
    filename = f"danh-sach-thuc-tap-{local_today().isoformat()}.{format}"
    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([label for _, label in COLUMNS])
        for r in rows:
            writer.writerow([r[k] for k, _ in COLUMNS])
        data = ("﻿" + buf.getvalue()).encode("utf-8")  # BOM để Excel đọc đúng tiếng Việt
        media = "text/csv; charset=utf-8"
    else:
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "Thực tập"
        ws.append([label for _, label in COLUMNS])
        for r in rows:
            ws.append([r[k] for k, _ in COLUMNS])
        out = io.BytesIO()
        wb.save(out)
        data = out.getvalue()
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return StreamingResponse(iter([data]), media_type=media,
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})
