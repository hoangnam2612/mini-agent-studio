"""Audit trail — ghi `audit_event` trong CÙNG transaction với thay đổi (P7).

`record_denied` là ngoại lệ: lần truy cập bị từ chối phải được ghi dù request
lỗi, nên dùng session riêng và commit ngay (R1.5, R15.3).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.db import session_factory
from src.models.orm import AuditEvent


@dataclass(frozen=True)
class Actor:
    """Ai đang hành động. kind=human mới có thể ra quyết định (design.md §3.1)."""

    kind: str  # human | system | agent
    user_id: int | None = None
    role: str = ""  # student | lecturer | admin

    @classmethod
    def system(cls) -> Actor:
        return cls(kind="system", role="system")


def record(
    db: Session,
    actor: Actor,
    entity: str,
    entity_id: int | None,
    action: str,
    before: dict | None = None,
    after: dict | None = None,
    reason: str = "",
) -> AuditEvent:
    event = AuditEvent(
        actor_id=actor.user_id,
        actor_kind=actor.kind,
        actor_role=actor.role,
        entity=entity,
        entity_id=entity_id,
        action=action,
        before=before,
        after=after,
        reason=reason or "",
    )
    db.add(event)
    return event


def record_denied(actor: Actor, entity: str, entity_id: int | None, detail: str) -> None:
    db = session_factory()()
    try:
        record(db, actor, entity, entity_id, "access_denied", reason=detail)
        db.commit()
    finally:
        db.close()
