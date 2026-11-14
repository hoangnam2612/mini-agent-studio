"""P1 (AI/system không bao giờ đi được cạnh quyết định) và P7 (mỗi chuyển trạng thái = 1 audit)."""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select

from src.core.audit import Actor
from src.models.orm import AuditEvent, ExtensionRequest, Internship, Outline
from src.workflow.state_machine import (
    DECISION_EDGES,
    STATE_GRAPH,
    ForbiddenTransition,
    InvalidTransition,
    ReasonRequired,
    transition,
)
from tests.test_vin15.conftest import internship_of

DECISION_CASES = [(kind, edge) for kind, edges in DECISION_EDGES.items() for edge in sorted(edges)]


def _entity(db, kind: str):
    model = {"internship": Internship, "outline": Outline, "extension": ExtensionRequest}[kind]
    return db.scalars(select(model)).first()


def test_decision_edges_cover_required_hitl_decisions():
    assert ("submitted", "approved") in DECISION_EDGES["internship"]
    assert ("submitted", "approved") in DECISION_EDGES["outline"]
    assert {("open", "approved"), ("open", "rejected")} <= DECISION_EDGES["extension"]
    for kind, edges in DECISION_EDGES.items():
        for edge in edges:
            assert STATE_GRAPH[kind][edge].actor_kinds == frozenset({"human"})


@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    case=st.sampled_from(DECISION_CASES),
    kind=st.sampled_from(["agent", "system"]),
    role=st.sampled_from(["lecturer", "admin", "student", "system", ""]),
    reason=st.text(max_size=20),
)
def test_p1_non_human_never_decides(db, case, kind, role, reason):
    entity_kind, (from_state, to_state) = case
    entity = _entity(db, entity_kind)
    entity.status = from_state
    owner = internship_of_entity(entity_kind, entity)
    actor = Actor(kind=kind, user_id=owner.lecturer_id, role=role)  # kể cả "mạo danh" đúng GV phụ trách
    with pytest.raises(ForbiddenTransition):
        transition(db, entity_kind, entity, to_state, actor, reason or "lý do")
    db.rollback()


def internship_of_entity(kind, entity):
    return entity if kind == "internship" else entity.internship if kind == "outline" else entity.milestone.internship


def test_decision_requires_assigned_lecturer(db):
    i = internship_of(db, "sv02")
    other_lecturer = 999
    with pytest.raises(ForbiddenTransition):
        transition(db, "internship", i, "approved", Actor("human", other_lecturer, "lecturer"))
    with pytest.raises(ForbiddenTransition):
        transition(db, "internship", i, "approved", Actor("human", i.student_id, "student"))


def test_reason_required_and_invalid_edge(db):
    i = internship_of(db, "sv02")
    gv = Actor("human", i.lecturer_id, "lecturer")
    with pytest.raises(ReasonRequired):
        transition(db, "internship", i, "rejected", gv, "  ")
    with pytest.raises(InvalidTransition):
        transition(db, "internship", i, "completed", gv)


def test_p7_each_transition_writes_exactly_one_audit_event(db):
    i = internship_of(db, "sv02")
    before = db.scalar(select(func.count(AuditEvent.id)))
    transition(db, "internship", i, "approved", Actor("human", i.lecturer_id, "lecturer"))
    db.flush()
    assert db.scalar(select(func.count(AuditEvent.id))) == before + 1
    event = db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc())).first()
    assert (event.entity, event.entity_id, event.action) == ("internship", i.id, "status:submitted->approved")
    assert event.after == {"status": "approved", "version": i.version} and event.actor_id == i.lecturer_id


def test_audit_is_append_only(db):
    from sqlalchemy.exc import DatabaseError

    event = db.scalars(select(AuditEvent)).first()
    event.reason = "sửa lịch sử"
    with pytest.raises(DatabaseError):
        db.commit()
    db.rollback()
    db.delete(db.scalars(select(AuditEvent)).first())
    with pytest.raises(DatabaseError):
        db.commit()
