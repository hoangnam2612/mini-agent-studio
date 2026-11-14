"""ORM models VIN-15 — bám bảng ở design.md §4.

Ghi chú:
- Ngày hạn (`due_date`, `start_date`…) là `date`; mốc thời gian sự kiện là `datetime` UTC naive.
- `RiskFlag.open_key` = "<internship>:<type>:<milestone>" khi cờ còn mở, NULL khi đóng.
  UNIQUE trên cột này chặn tạo trùng cờ đang mở ở cả SQLite lẫn Postgres (R10.4, P4).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db import Base


def utcnow() -> datetime:
    """UTC naive — SQLite không lưu tzinfo, giữ một quy ước cho cả hai DB."""
    return datetime.now(UTC).replace(tzinfo=None)


class User(Base):
    __tablename__ = "user_account"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(16))  # student | lecturer | admin
    full_name: Mapped[str] = mapped_column(String(128))
    email: Mapped[str] = mapped_column(String(128), default="")
    phone: Mapped[str] = mapped_column(String(32), default="")
    student_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    program: Mapped[str] = mapped_column(String(128), default="")
    is_coordinator: Mapped[bool] = mapped_column(Boolean, default=False)
    # Phân công GV cho SV (R1.4) — None với vai trò khác student
    lecturer_id: Mapped[int | None] = mapped_column(ForeignKey("user_account.id"), nullable=True)


class Cohort(Base):
    __tablename__ = "cohort"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    start_window: Mapped[date] = mapped_column(Date)
    end_window: Mapped[date] = mapped_column(Date)
    min_weeks: Mapped[int] = mapped_column(Integer)
    hours_per_week: Mapped[int] = mapped_column(Integer)
    outcomes: Mapped[list] = mapped_column(JSON, default=list)  # [{code, text, keywords}]
    rules: Mapped[dict] = mapped_column(JSON, default=dict)  # validation + monitor (cohort.yaml)

    templates: Mapped[list[MilestoneTemplate]] = relationship(
        back_populates="cohort", order_by="MilestoneTemplate.ordinal", cascade="all, delete-orphan"
    )


class MilestoneTemplate(Base):
    __tablename__ = "milestone_template"

    id: Mapped[int] = mapped_column(primary_key=True)
    cohort_id: Mapped[int] = mapped_column(ForeignKey("cohort.id"))
    code: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(128))
    ordinal: Mapped[int] = mapped_column(Integer, default=0)
    due_rule: Mapped[dict] = mapped_column(JSON)  # {"anchor": start|mid|end, "offset_days": n}
    required_evidence: Mapped[list] = mapped_column(JSON, default=list)
    citation: Mapped[dict] = mapped_column(JSON, default=dict)
    linked_to: Mapped[str | None] = mapped_column(String(32), nullable=True)  # "outline" = mốc gắn đề cương

    cohort: Mapped[Cohort] = relationship(back_populates="templates")


class Company(Base):
    __tablename__ = "company"

    id: Mapped[int] = mapped_column(primary_key=True)
    tax_code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(256))
    address: Mapped[str] = mapped_column(String(512), default="")


class Internship(Base):
    __tablename__ = "internship"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("user_account.id"))
    lecturer_id: Mapped[int | None] = mapped_column(ForeignKey("user_account.id"), nullable=True)
    cohort_id: Mapped[int] = mapped_column(ForeignKey("cohort.id"))
    company_id: Mapped[int | None] = mapped_column(ForeignKey("company.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="draft")
    company_name: Mapped[str] = mapped_column(String(256), default="")
    company_tax_code: Mapped[str] = mapped_column(String(20), default="")
    company_address: Mapped[str] = mapped_column(String(512), default="")
    mentor_name: Mapped[str] = mapped_column(String(128), default="")
    mentor_email: Mapped[str] = mapped_column(String(128), default="")
    mentor_phone: Mapped[str] = mapped_column(String(32), default="")
    position: Mapped[str] = mapped_column(String(128), default="")
    job_description: Mapped[str] = mapped_column(Text, default="")
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    mode: Mapped[str] = mapped_column(String(16), default="full_time")  # full_time | part_time
    ai_fields: Mapped[list] = mapped_column(JSON, default=list)  # tên trường do AI điền (R2.6)
    decision_reason: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    student: Mapped[User] = relationship(foreign_keys=[student_id])
    lecturer: Mapped[User | None] = relationship(foreign_keys=[lecturer_id])
    cohort: Mapped[Cohort] = relationship()
    milestones: Mapped[list[Milestone]] = relationship(
        back_populates="internship", order_by="Milestone.ordinal", cascade="all, delete-orphan"
    )
    outline: Mapped[Outline | None] = relationship(back_populates="internship", uselist=False)
    logs: Mapped[list[LogEntry]] = relationship(back_populates="internship", order_by="LogEntry.week_no")


class Outline(Base):
    __tablename__ = "outline"

    id: Mapped[int] = mapped_column(primary_key=True)
    internship_id: Mapped[int] = mapped_column(ForeignKey("internship.id"), unique=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    content: Mapped[str] = mapped_column(Text)
    ai_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="submitted")
    reason: Mapped[str] = mapped_column(Text, default="")
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("user_account.id"), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    internship: Mapped[Internship] = relationship(back_populates="outline")


class Milestone(Base):
    __tablename__ = "milestone"

    id: Mapped[int] = mapped_column(primary_key=True)
    internship_id: Mapped[int] = mapped_column(ForeignKey("internship.id"))
    template_id: Mapped[int | None] = mapped_column(ForeignKey("milestone_template.id"), nullable=True)
    code: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(128))
    ordinal: Mapped[int] = mapped_column(Integer, default=0)
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    required_evidence: Mapped[list] = mapped_column(JSON, default=list)
    citation: Mapped[dict] = mapped_column(JSON, default=dict)
    linked_to: Mapped[str | None] = mapped_column(String(32), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    comment: Mapped[str] = mapped_column(Text, default="")

    internship: Mapped[Internship] = relationship(back_populates="milestones")
    evidence: Mapped[list[Evidence]] = relationship(back_populates="milestone")


class LogEntry(Base):
    __tablename__ = "log_entry"
    __table_args__ = (UniqueConstraint("internship_id", "week_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    internship_id: Mapped[int] = mapped_column(ForeignKey("internship.id"))
    week_no: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    difficulties: Mapped[str] = mapped_column(Text, default="")
    hours: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | accepted | returned
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    internship: Mapped[Internship] = relationship(back_populates="logs")
    attachments: Mapped[list[Evidence]] = relationship(back_populates="log_entry")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    milestone_id: Mapped[int | None] = mapped_column(ForeignKey("milestone.id"), nullable=True)
    log_entry_id: Mapped[int | None] = mapped_column(ForeignKey("log_entry.id"), nullable=True)
    internship_id: Mapped[int] = mapped_column(ForeignKey("internship.id"))
    evidence_type: Mapped[str] = mapped_column(String(32), default="other")
    filename: Mapped[str] = mapped_column(String(256))
    path: Mapped[str] = mapped_column(String(512))
    mime: Mapped[str] = mapped_column(String(128))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("user_account.id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    milestone: Mapped[Milestone | None] = relationship(back_populates="evidence")
    log_entry: Mapped[LogEntry | None] = relationship(back_populates="attachments")


class ExtensionRequest(Base):
    __tablename__ = "extension_request"

    id: Mapped[int] = mapped_column(primary_key=True)
    milestone_id: Mapped[int] = mapped_column(ForeignKey("milestone.id"))
    requested_by: Mapped[int] = mapped_column(ForeignKey("user_account.id"))
    previous_due_date: Mapped[date] = mapped_column(Date)
    requested_due_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text)
    evidence_id: Mapped[int | None] = mapped_column(ForeignKey("evidence.id"), nullable=True)
    ai_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="open")
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("user_account.id"), nullable=True)
    decision_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    milestone: Mapped[Milestone] = relationship()


class RiskFlag(Base):
    __tablename__ = "risk_flag"

    id: Mapped[int] = mapped_column(primary_key=True)
    internship_id: Mapped[int] = mapped_column(ForeignKey("internship.id"))
    milestone_id: Mapped[int | None] = mapped_column(ForeignKey("milestone.id"), nullable=True)
    flag_type: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(16))  # info | warning | critical
    reason: Mapped[str] = mapped_column(Text)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open|acknowledged|resolved|dismissed
    open_key: Mapped[str | None] = mapped_column(String(96), unique=True, nullable=True)
    resolution_note: Mapped[str] = mapped_column(Text, default="")
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("user_account.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    internship: Mapped[Internship] = relationship()


class Notification(Base):
    __tablename__ = "notification"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_account.id"))
    kind: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(256))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PolicyDoc(Base):
    __tablename__ = "policy_doc"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(256))
    issuer: Mapped[str] = mapped_column(String(256), default="")
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("policy_doc.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | superseded
    filename: Mapped[str] = mapped_column(String(256), default="")
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("user_account.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    chunks: Mapped[list[PolicyChunk]] = relationship(
        back_populates="doc", order_by="PolicyChunk.ordinal", cascade="all, delete-orphan"
    )


class PolicyChunk(Base):
    __tablename__ = "policy_chunk"

    id: Mapped[int] = mapped_column(primary_key=True)
    doc_id: Mapped[int] = mapped_column(ForeignKey("policy_doc.id"))
    ordinal: Mapped[int] = mapped_column(Integer)
    path: Mapped[str] = mapped_column(String(128))  # "Chương II / Điều 5 / Khoản 1"
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)  # vector khi có embedder (R9.2)

    doc: Mapped[PolicyDoc] = relationship(back_populates="chunks")


class Conversation(Base):
    __tablename__ = "conversation"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_account.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    messages: Mapped[list[Message]] = relationship(back_populates="conversation", order_by="Message.id")


class Message(Base):
    __tablename__ = "message"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversation.id"))
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    citations: Mapped[list[Citation]] = relationship(back_populates="message")


class Citation(Base):
    __tablename__ = "citation"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("message.id"))
    chunk_id: Mapped[int] = mapped_column(ForeignKey("policy_chunk.id"))
    label: Mapped[str] = mapped_column(String(256))

    message: Mapped[Message] = relationship(back_populates="citations")


class AuditEvent(Base):
    """Append-only — trigger DB chặn UPDATE/DELETE (xem src/db.py)."""

    __tablename__ = "audit_event"

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_kind: Mapped[str] = mapped_column(String(16))  # human | system | agent
    actor_role: Mapped[str] = mapped_column(String(16), default="")
    entity: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
