"""Chuyển ORM → dict trả về client. Gom một chỗ để dễ kiểm soát trường nào lộ ra ngoài."""

from __future__ import annotations

from datetime import date

from src.models.orm import (
    Evidence,
    ExtensionRequest,
    Internship,
    LogEntry,
    Milestone,
    Notification,
    Outline,
    PolicyDoc,
    RiskFlag,
    User,
)

INTERNSHIP_FIELDS = (
    "company_name", "company_tax_code", "company_address", "mentor_name", "mentor_email", "mentor_phone",
    "position", "job_description", "start_date", "end_date", "mode",
)


def _d(value) -> str | None:
    return value.isoformat() if value else None


def user_out(u: User) -> dict:
    return {
        "id": u.id, "username": u.username, "role": u.role, "full_name": u.full_name, "email": u.email,
        "student_code": u.student_code, "program": u.program, "is_coordinator": u.is_coordinator,
        "lecturer_id": u.lecturer_id,
    }


def evidence_out(e: Evidence) -> dict:
    return {"id": e.id, "evidence_type": e.evidence_type, "filename": e.filename, "mime": e.mime,
            "size": e.size, "uploaded_at": _d(e.uploaded_at)}


def milestone_out(m: Milestone, today: date | None = None) -> dict:
    today = today or date.today()
    return {
        "id": m.id, "code": m.code, "name": m.name, "due_date": _d(m.due_date), "status": m.status,
        "days_left": (m.due_date - today).days, "required_evidence": m.required_evidence,
        "citation": m.citation, "linked_to": m.linked_to, "submitted_at": _d(m.submitted_at),
        "comment": m.comment, "evidence": [evidence_out(e) for e in m.evidence],
    }


def outline_out(o: Outline | None) -> dict | None:
    if o is None:
        return None
    return {"id": o.id, "version": o.version, "content": o.content, "status": o.status, "reason": o.reason,
            "ai_summary": o.ai_summary, "submitted_at": _d(o.submitted_at)}


def internship_out(i: Internship, detail: bool = False) -> dict:
    data = {
        "id": i.id, "status": i.status, "version": i.version,
        "student": {"id": i.student.id, "full_name": i.student.full_name, "student_code": i.student.student_code},
        "lecturer": {"id": i.lecturer.id, "full_name": i.lecturer.full_name} if i.lecturer else None,
        "cohort": {"id": i.cohort.id, "code": i.cohort.code, "name": i.cohort.name},
        "ai_fields": i.ai_fields or [], "decision_reason": i.decision_reason,
        **{f: _d(getattr(i, f)) if f.endswith("_date") else getattr(i, f) for f in INTERNSHIP_FIELDS},
    }
    if detail:
        data["milestones"] = [milestone_out(m) for m in i.milestones]
        data["outline"] = outline_out(i.outline)
    return data


def log_out(log: LogEntry) -> dict:
    return {"id": log.id, "week_no": log.week_no, "content": log.content, "difficulties": log.difficulties,
            "hours": log.hours, "review_status": log.status, "comment": log.comment,
            "attachments": [evidence_out(e) for e in log.attachments], "created_at": _d(log.created_at)}


def extension_out(e: ExtensionRequest) -> dict:
    i = e.milestone.internship
    return {
        "id": e.id, "status": e.status, "milestone": {"id": e.milestone.id, "name": e.milestone.name,
                                                       "due_date": _d(e.milestone.due_date)},
        "internship_id": i.id, "student": {"id": i.student.id, "full_name": i.student.full_name},
        "previous_due_date": _d(e.previous_due_date), "requested_due_date": _d(e.requested_due_date),
        "reason": e.reason, "evidence_id": e.evidence_id, "ai_summary": e.ai_summary,
        "decision_reason": e.decision_reason, "created_at": _d(e.created_at), "decided_at": _d(e.decided_at),
    }


def flag_out(f: RiskFlag) -> dict:
    return {
        "id": f.id, "internship_id": f.internship_id, "milestone_id": f.milestone_id, "flag_type": f.flag_type,
        "severity": f.severity, "reason": f.reason, "evidence_refs": f.evidence_refs, "status": f.status,
        "resolution_note": f.resolution_note, "created_at": _d(f.created_at),
        "student": {"id": f.internship.student.id, "full_name": f.internship.student.full_name},
    }


def notification_out(n: Notification) -> dict:
    return {"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": n.link,
            "created_at": _d(n.created_at), "read": n.read_at is not None}


def policy_out(p: PolicyDoc) -> dict:
    return {"id": p.id, "code": p.code, "title": p.title, "issuer": p.issuer, "status": p.status,
            "effective_from": _d(p.effective_from), "effective_to": _d(p.effective_to),
            "supersedes_id": p.supersedes_id, "chunk_count": len(p.chunks), "filename": p.filename}
