"""State machine + `transition()` — cổng DUY NHẤT để đổi trạng thái (design.md §3.1).

Bất biến cứng (C1, R3.4, R10.6, P1): cạnh nằm trong DECISION_EDGES chỉ đi
được khi actor là con người, đúng vai trò GV và là GV phụ trách. Agent và
tiến trình hệ thống gọi vào sẽ bị raise ForbiddenTransition — ràng buộc
nằm ở code, không phụ thuộc prompt.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.core import audit
from src.core.audit import Actor
from src.models.orm import ExtensionRequest, Internship, LogEntry, Milestone, Outline


class TransitionError(Exception):
    status_code = 400


class InvalidTransition(TransitionError):  # noqa: N818
    status_code = 409


class ForbiddenTransition(TransitionError):  # noqa: N818
    status_code = 403


class ReasonRequired(TransitionError):  # noqa: N818
    status_code = 422


@dataclass(frozen=True)
class EdgeRule:
    actor_kinds: frozenset[str]
    roles: frozenset[str] = frozenset()  # rỗng = không xét vai trò (system)
    owner: str = ""  # "student" | "lecturer" | "" — phải là SV sở hữu / GV phụ trách
    decision: bool = False
    reason_required: bool = False


_STUDENT = EdgeRule(frozenset({"human"}), frozenset({"student"}), owner="student")
_LECTURER = EdgeRule(frozenset({"human"}), frozenset({"lecturer"}), owner="lecturer")
_DECISION = EdgeRule(frozenset({"human"}), frozenset({"lecturer"}), owner="lecturer", decision=True)
_DECISION_REASON = EdgeRule(
    frozenset({"human"}), frozenset({"lecturer"}), owner="lecturer", decision=True, reason_required=True
)
_SYSTEM = EdgeRule(frozenset({"system"}))

STATE_GRAPH: dict[str, dict[tuple[str, str], EdgeRule]] = {
    "internship": {
        ("draft", "submitted"): _STUDENT,
        ("revision_requested", "submitted"): _STUDENT,
        ("submitted", "approved"): _DECISION,
        ("submitted", "rejected"): _DECISION_REASON,
        ("submitted", "revision_requested"): _DECISION_REASON,
        ("approved", "in_progress"): _SYSTEM,
        ("in_progress", "completed"): _SYSTEM,
    },
    "outline": {
        ("revision_requested", "submitted"): _STUDENT,
        ("rejected", "submitted"): _STUDENT,
        ("submitted", "approved"): _DECISION,
        ("submitted", "rejected"): _DECISION_REASON,
        ("submitted", "revision_requested"): _DECISION_REASON,
    },
    "milestone": {
        ("pending", "submitted"): _STUDENT,
        ("overdue", "submitted"): _STUDENT,
        ("rejected", "submitted"): _STUDENT,
        ("submitted", "accepted"): _LECTURER,
        ("submitted", "rejected"): _LECTURER,
        ("pending", "overdue"): _SYSTEM,
        ("rejected", "overdue"): _SYSTEM,
        # Gỡ overdue chỉ xảy ra trong apply_extension (P8) — actor là GV đã duyệt gia hạn
        ("overdue", "pending"): _LECTURER,
    },
    "extension": {
        ("open", "approved"): _DECISION_REASON,
        ("open", "rejected"): _DECISION_REASON,
        ("open", "cancelled"): _STUDENT,
    },
    "log_entry": {
        ("pending", "accepted"): _LECTURER,
        ("pending", "returned"): _LECTURER,
        ("returned", "pending"): _STUDENT,
    },
}

# Tập cạnh quyết định — test P1 duyệt toàn bộ tập này
DECISION_EDGES: dict[str, set[tuple[str, str]]] = {
    kind: {edge for edge, rule in edges.items() if rule.decision} for kind, edges in STATE_GRAPH.items()
}


def internship_of(kind: str, entity) -> Internship:
    if kind == "internship":
        return entity
    if kind in ("outline", "milestone", "log_entry"):
        return entity.internship
    if kind == "extension":
        return entity.milestone.internship
    raise ValueError(f"Loại thực thể không hỗ trợ: {kind}")


def _owner_ok(rule: EdgeRule, actor: Actor, internship: Internship) -> bool:
    if rule.owner == "student":
        return actor.user_id == internship.student_id
    if rule.owner == "lecturer":
        return actor.user_id is not None and actor.user_id == internship.lecturer_id
    return True


def transition(
    db: Session,
    kind: str,
    entity: Internship | Outline | Milestone | ExtensionRequest | LogEntry,
    to_state: str,
    actor: Actor,
    reason: str | None = None,
) -> None:
    """Đổi trạng thái + ghi audit trong cùng transaction (caller commit)."""
    from_state = entity.status
    rule = STATE_GRAPH[kind].get((from_state, to_state))
    if rule is None:
        raise InvalidTransition(f"Không thể chuyển {kind} từ '{from_state}' sang '{to_state}'")
    internship = internship_of(kind, entity)
    if (
        actor.kind not in rule.actor_kinds
        or (rule.roles and actor.role not in rule.roles)
        or not _owner_ok(rule, actor, internship)
    ):
        raise ForbiddenTransition(
            f"{actor.kind}/{actor.role or '-'} không được phép chuyển {kind} '{from_state}' → '{to_state}'"
        )
    if rule.reason_required and not (reason and reason.strip()):
        raise ReasonRequired("Quyết định này bắt buộc nhập lý do")
    entity.status = to_state
    after: dict = {"status": to_state}
    if getattr(entity, "version", None) is not None:
        after["version"] = entity.version  # R3.5: quyết định gắn với đúng phiên bản hồ sơ/đề cương
    audit.record(
        db,
        actor,
        kind,
        entity.id,
        f"status:{from_state}->{to_state}",
        before={"status": from_state},
        after=after,
        reason=reason or "",
    )
