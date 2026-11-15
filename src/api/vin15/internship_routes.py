"""Hồ sơ đăng ký, AI chuẩn hóa, đề cương, phê duyệt (R2, R3)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.api.vin15.auth_routes import current_cohort
from src.api.vin15.deps import load_internship, load_outline, scoped_internships
from src.api.vin15.serializers import INTERNSHIP_FIELDS, extension_out, internship_out, outline_out
from src.config import get_settings
from src.core import audit, ratelimit
from src.core.audit import Actor
from src.core.auth import actor_of, current_user, require_role
from src.db import get_db, session_factory
from src.models.orm import AuditEvent, Company, ExtensionRequest, Internship, Milestone, Outline, User
from src.services import intake, lifecycle, monitor
from src.services.documents import IMAGE_EXTS, UnreadableDocument, read_document
from src.services.llm import llm_available
from src.services.notifications import notify
from src.services.pii import Redactor
from src.services.provenance import document_payload
from src.services.reviewer import summarize_outline
from src.services.storage import ALLOWED, FileRejected, check_file
from src.workflow.rules import validate_internship
from src.workflow.state_machine import transition

router = APIRouter(tags=["internships"])

_EDITABLE = ("draft", "revision_requested")
_TEXT_TYPES = {".txt": ("text/plain", (b"",))}


def _intake_types() -> dict:
    """PDF/DOCX/TXT luôn nhận; ảnh chỉ nhận khi bật OCR (dùng lại định nghĩa magic bytes của storage)."""
    exts = (".pdf", ".docx") + (IMAGE_EXTS if get_settings().ocr_enabled else ())
    return {**{e: ALLOWED[e] for e in exts}, **_TEXT_TYPES}


class InternshipIn(BaseModel):
    company_name: str | None = Field(default=None, max_length=256)
    company_tax_code: str | None = Field(default=None, max_length=20)
    company_address: str | None = Field(default=None, max_length=512)
    mentor_name: str | None = Field(default=None, max_length=128)
    mentor_email: str | None = Field(default=None, max_length=128)
    mentor_phone: str | None = Field(default=None, max_length=32)
    position: str | None = Field(default=None, max_length=128)
    job_description: str | None = Field(default=None, max_length=5000)
    start_date: date | None = None
    end_date: date | None = None
    mode: Literal["full_time", "part_time"] | None = None
    ai_fields: list[str] | None = None  # trường SV đã nhận từ gợi ý AI (R2.6)
    version: int | None = None


class DecisionIn(BaseModel):
    decision: Literal["approved", "rejected", "revision_requested"]
    reason: str = Field(default="", max_length=2000)
    version: int


class OutlineIn(BaseModel):
    content: str = Field(min_length=50, max_length=20000)


def _apply_fields(i: Internship, body: InternshipIn) -> dict:
    changed = {}
    for field in INTERNSHIP_FIELDS:
        value = getattr(body, field)
        if value is None:
            continue
        if field == "company_tax_code":
            value = intake.normalize_tax_code(value) or value.strip()
        elif field == "mentor_email":
            value = intake.normalize_email(value) or value.strip()
        elif field == "mentor_phone":
            value = intake.normalize_phone(value) or value.strip()
        elif isinstance(value, str):
            value = value.strip()
        if getattr(i, field) != value:
            changed[field] = str(value)
            setattr(i, field, value)
    if body.ai_fields is not None:
        i.ai_fields = [f for f in body.ai_fields if f in INTERNSHIP_FIELDS]
    return changed


@router.get("/internships")
def list_internships(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(scoped_internships(user).order_by(Internship.id.desc())).all()
    return [internship_out(i) for i in rows]


@router.get("/internships/{internship_id}")
def get_internship(internship_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return internship_out(load_internship(db, user, internship_id), detail=True)


@router.post("/internships", status_code=201)
def create_internship(body: InternshipIn, user: User = Depends(require_role("student")),
                      db: Session = Depends(get_db)) -> dict:
    cohort = current_cohort(db)
    active = db.scalar(select(Internship).where(
        Internship.student_id == user.id, Internship.cohort_id == cohort.id, Internship.status != "rejected"))
    if active:
        raise HTTPException(status_code=409, detail="Bạn đã có hồ sơ thực tập trong đợt này")
    if user.lecturer_id is None:
        raise HTTPException(status_code=422, detail="Bạn chưa được phân công giảng viên phụ trách")
    i = Internship(student_id=user.id, lecturer_id=user.lecturer_id, cohort_id=cohort.id)
    db.add(i)
    _apply_fields(i, body)
    db.flush()
    audit.record(db, actor_of(user), "internship", i.id, "created")
    db.commit()
    return internship_out(i, detail=True)


@router.patch("/internships/{internship_id}")
def update_internship(internship_id: int, body: InternshipIn, user: User = Depends(require_role("student")),
                      db: Session = Depends(get_db)) -> dict:
    i = load_internship(db, user, internship_id)
    if i.status not in _EDITABLE:
        raise HTTPException(status_code=409, detail="Chỉ sửa được hồ sơ ở trạng thái nháp hoặc cần chỉnh sửa")
    if body.version is not None and body.version != i.version:
        raise HTTPException(status_code=409, detail="Hồ sơ đã thay đổi, hãy tải lại")
    changed = _apply_fields(i, body)
    if changed:
        i.version += 1
        audit.record(db, actor_of(user), "internship", i.id, "updated", after=changed)
    db.commit()
    return internship_out(i, detail=True)


def _validation(i: Internship) -> list[dict]:
    return [
        {"rule_id": r.rule_id, "passed": r.passed, "message": r.message, "citation": r.citation}
        for r in validate_internship(i, i.cohort)
    ]


@router.post("/internships/{internship_id}/validate")
def validate(internship_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    results = _validation(load_internship(db, user, internship_id))
    return {"ok": all(r["passed"] for r in results), "results": results}


@router.post("/internships/{internship_id}/submit")
def submit(internship_id: int, user: User = Depends(require_role("student")), db: Session = Depends(get_db)) -> dict:
    i = load_internship(db, user, internship_id)
    errors = [r for r in _validation(i) if not r["passed"]]
    if errors:
        raise HTTPException(status_code=422, detail={"message": "Hồ sơ chưa đạt yêu cầu quy chế", "errors": errors})
    company = db.scalar(select(Company).where(Company.tax_code == i.company_tax_code))
    if company is None:
        company = Company(tax_code=i.company_tax_code, name=intake.normalize_company_name(i.company_name) or i.company_name,
                          address=i.company_address)
        db.add(company)
        db.flush()
    i.company_id = company.id
    transition(db, "internship", i, "submitted", actor_of(user))
    notify(db, i.lecturer_id, "approval", f"Hồ sơ thực tập mới chờ duyệt: {user.full_name}", link="#/queue")
    db.commit()
    return internship_out(i, detail=True)


@router.post("/internships/{internship_id}/decision")
def decide_internship(internship_id: int, body: DecisionIn, user: User = Depends(require_role("lecturer")),
                      db: Session = Depends(get_db)) -> dict:
    i = load_internship(db, user, internship_id)
    if body.version != i.version:
        raise HTTPException(status_code=409, detail="Hồ sơ đã được sinh viên sửa sau khi bạn mở — hãy tải lại")
    transition(db, "internship", i, body.decision, actor_of(user), body.reason)
    i.decision_reason = body.reason.strip()
    if body.decision == "approved":
        lifecycle.generate_milestones(i)
        db.flush()
        if i.start_date and i.start_date <= date.today():
            transition(db, "internship", i, "in_progress", Actor.system())
        monitor.run_for_event(db, i)
    labels = {"approved": "được duyệt", "rejected": "bị từ chối", "revision_requested": "cần chỉnh sửa"}
    notify(db, i.student_id, "decision", f"Hồ sơ thực tập {labels[body.decision]}", body.reason, link="#/")
    db.commit()
    return internship_out(i, detail=True)


class IntakeError(Exception):
    """Không đọc/trích được giấy tiếp nhận (→ 422, hoặc sự kiện `error` khi stream)."""


async def _run_intake(db: Session, user: User, name: str, content: bytes, emit: Callable[[dict], None] | None = None) -> dict:
    """Đọc file (OCR nếu là scan/ảnh) → trích trường → gắn vị trí nguồn. `emit` nhận các sự kiện tiến độ."""
    loop = asyncio.get_running_loop()

    def say(event: dict) -> None:
        if emit:
            emit(event)

    def on_progress(event: dict) -> None:  # gọi từ thread đang đọc file
        if emit and event.get("stage") == "ocr":
            label = f"Nhận dạng chữ trên ảnh — trang {event['page']}/{event['pages']}"
            loop.call_soon_threadsafe(emit, {"type": "stage", **event, "label": label})

    say({"type": "stage", "stage": "read", "label": "Đọc nội dung file"})
    try:
        # OCR chạy CPU và chặn → để ngoài event loop (SSE trợ lý, monitor dùng chung process)
        doc = await run_in_threadpool(read_document, name, content, ocr=True, progress=on_progress)
    except UnreadableDocument as exc:
        raise IntakeError(str(exc)) from exc
    if not doc.text.strip():
        raise IntakeError("Không đọc được chữ trong file — hãy tải bản rõ hơn hoặc nhập tay")
    say({"type": "stage", "stage": "extract",
         "label": "Trích xuất các trường bằng mô hình AI" if llm_available() else "Trích xuất các trường theo luật"})
    redactor = Redactor({"HO_TEN": user.full_name, "MSSV": user.student_code, "EMAIL": user.email})
    result = await intake.extract_suggestions(db, doc.text, redactor, from_ocr=doc.used_ocr, doc=doc)
    result["document"] = document_payload(doc)
    return result


async def _read_upload(file: UploadFile, user: User) -> tuple[str, bytes]:
    ratelimit.enforce_usage(user.id, "intake", get_settings().intake_per_minute)
    content = await file.read()
    name = file.filename or "upload"
    try:
        check_file(name, content, _intake_types())
    except FileRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return name, content


@router.post("/intake/extract")
async def intake_extract(file: UploadFile = File(...), user: User = Depends(require_role("student")),
                         db: Session = Depends(get_db)) -> dict:
    name, content = await _read_upload(file, user)
    try:
        return await _run_intake(db, user, name, content)
    except IntakeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/intake/extract/stream")
async def intake_extract_stream(file: UploadFile = File(...), user: User = Depends(require_role("student"))) -> StreamingResponse:
    """SSE: `stage` (read / ocr theo trang / extract) → `done` kèm kết quả, hoặc `error`. Cùng kết quả với /intake/extract."""
    name, content = await _read_upload(file, user)  # lỗi định dạng/giới hạn → HTTP 4xx như thường, chưa mở stream
    queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def worker() -> None:
        db = session_factory()()
        try:
            queue.put_nowait({"type": "stage", "stage": "upload", "label": "Đã nhận file"})
            result = await _run_intake(db, user, name, content, queue.put_nowait)
            queue.put_nowait({"type": "done", "result": result})
        except IntakeError as exc:
            queue.put_nowait({"type": "error", "detail": str(exc)})
        except Exception as exc:  # lỗi bất ngờ → báo tường minh cho client, không im lặng
            queue.put_nowait({"type": "error", "detail": f"Lỗi khi xử lý file: {exc}"})
        finally:
            db.close()
            queue.put_nowait(None)

    task = asyncio.create_task(worker())

    async def events():
        try:
            while (event := await queue.get()) is not None:
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        finally:
            task.cancel()  # client ngắt kết nối giữa chừng → thôi chờ kết quả

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------- đề cương (R3)

@router.post("/internships/{internship_id}/outline")
def submit_outline(internship_id: int, body: OutlineIn, user: User = Depends(require_role("student")),
                   db: Session = Depends(get_db)) -> dict:
    i = load_internship(db, user, internship_id)
    if i.status not in ("approved", "in_progress"):
        raise HTTPException(status_code=409, detail="Chỉ nộp đề cương sau khi hồ sơ đăng ký được duyệt")
    actor = actor_of(user)
    o = i.outline
    if o is None:
        o = Outline(internship_id=i.id, content=body.content)
        db.add(o)
        db.flush()
        audit.record(db, actor, "outline", o.id, "submitted")
    elif o.status in ("revision_requested", "rejected"):
        o.content = body.content
        o.version += 1
        transition(db, "outline", o, "submitted", actor)
    else:
        raise HTTPException(status_code=409, detail="Đề cương đang chờ duyệt hoặc đã được duyệt")
    redactor = Redactor({"HO_TEN": user.full_name, "MSSV": user.student_code, "EMAIL": user.email})
    o.ai_summary = summarize_outline(o.content, i.cohort, redactor)
    db.flush()
    db.refresh(i)
    lifecycle.on_outline_submitted(db, i, actor)
    notify(db, i.lecturer_id, "approval", f"Đề cương mới chờ duyệt: {user.full_name}", link="#/queue")
    db.commit()
    return outline_out(o)


@router.post("/outlines/{outline_id}/decision")
def decide_outline(outline_id: int, body: DecisionIn, user: User = Depends(require_role("lecturer")),
                   db: Session = Depends(get_db)) -> dict:
    o = load_outline(db, user, outline_id)
    if body.version != o.version:
        raise HTTPException(status_code=409, detail="Đề cương đã được sửa sau khi bạn mở — hãy tải lại")
    actor = actor_of(user)
    transition(db, "outline", o, body.decision, actor, body.reason)
    o.reason = body.reason.strip()
    o.decided_by = user.id
    # Mốc gắn đề cương: duyệt → accepted; từ chối / yêu cầu sửa → rejected (SV nộp lại)
    lifecycle.on_outline_decided(
        db, o.internship, "approved" if body.decision == "approved" else "rejected", actor, body.reason
    )
    labels = {"approved": "được duyệt", "rejected": "bị từ chối", "revision_requested": "cần chỉnh sửa"}
    notify(db, o.internship.student_id, "decision", f"Đề cương {labels[body.decision]}", body.reason, link="#/")
    monitor.run_for_event(db, o.internship)
    db.commit()
    return outline_out(o)


@router.get("/approvals/queue")
def approval_queue(user: User = Depends(require_role("lecturer")), db: Session = Depends(get_db)) -> dict:
    internships = db.scalars(select(Internship).where(
        Internship.lecturer_id == user.id, Internship.status == "submitted").order_by(Internship.updated_at)).all()
    outlines = db.scalars(select(Outline).join(Internship).where(
        Internship.lecturer_id == user.id, Outline.status == "submitted").order_by(Outline.submitted_at)).all()
    extensions = db.scalars(select(ExtensionRequest).join(Milestone).join(Internship).where(
        Internship.lecturer_id == user.id, ExtensionRequest.status == "open").order_by(ExtensionRequest.created_at)).all()
    return {
        "internships": [internship_out(i) for i in internships],
        "outlines": [{**outline_out(o), "internship": internship_out(o.internship)} for o in outlines],
        "extensions": [extension_out(e) for e in extensions],
    }


@router.get("/internships/{internship_id}/audit")
def internship_audit(internship_id: int, user: User = Depends(require_role("lecturer", "admin")),
                     db: Session = Depends(get_db)) -> list[dict]:
    i = load_internship(db, user, internship_id)
    keys = [("internship", i.id)]
    keys += [("milestone", m.id) for m in i.milestones]
    if i.outline:
        keys.append(("outline", i.outline.id))
    keys += [("log_entry", log.id) for log in i.logs]
    ext_ids = db.scalars(select(ExtensionRequest.id).join(Milestone).where(Milestone.internship_id == i.id)).all()
    keys += [("extension", e) for e in ext_ids]
    conditions = [(AuditEvent.entity == e) & (AuditEvent.entity_id == eid) for e, eid in keys]
    events = db.scalars(select(AuditEvent).where(or_(*conditions)).order_by(AuditEvent.id)).all()
    names = {u.id: u.full_name for u in db.scalars(select(User).where(
        User.id.in_({e.actor_id for e in events if e.actor_id}))).all()}
    return [
        {"id": e.id, "at": e.at.isoformat(), "actor": names.get(e.actor_id, e.actor_kind), "actor_kind": e.actor_kind,
         "entity": e.entity, "entity_id": e.entity_id, "action": e.action, "reason": e.reason,
         "before": e.before, "after": e.after}
        for e in events
    ]
