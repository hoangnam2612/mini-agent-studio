"""Trợ lý AI chính sách (R8) + kho văn bản quy định (R9)."""

from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.agents.policy_graph import answer_policy_question, stream_policy_answer
from src.api.vin15.serializers import policy_out
from src.config import get_settings
from src.core import audit, ratelimit
from src.core.auth import actor_of, can_manage_policies, current_user
from src.db import get_db, session_factory
from src.models.orm import Citation, Conversation, Internship, Message, PolicyChunk, PolicyDoc, User
from src.services import policy_index
from src.services.documents import UnreadableDocument, extract_text

router = APIRouter(tags=["assistant"])

_STATUS_VI = {
    "draft": "đang soạn hồ sơ", "submitted": "hồ sơ chờ duyệt", "revision_requested": "hồ sơ cần chỉnh sửa",
    "approved": "hồ sơ đã duyệt, chưa bắt đầu", "in_progress": "đang thực tập", "completed": "đã hoàn thành",
    "rejected": "hồ sơ bị từ chối",
}


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: int | None = None


def _student_context(db: Session, user: User) -> dict:
    """Ngữ cảnh tối thiểu (R8.2) — không có họ tên, MSSV, email, SĐT."""
    ctx: dict = {"Vai trò": {"student": "sinh viên", "lecturer": "giảng viên", "admin": "quản trị viên"}[user.role]}
    if user.role != "student":
        return ctx
    ctx["Ngành"] = user.program or "(chưa rõ)"
    i = db.scalar(select(Internship).where(Internship.student_id == user.id).order_by(Internship.id.desc()))
    if i is None:
        ctx["Trạng thái hồ sơ"] = "chưa có hồ sơ"
        return ctx
    ctx["Đợt"] = i.cohort.name
    ctx["Trạng thái hồ sơ"] = _STATUS_VI.get(i.status, i.status)
    ctx["Hình thức"] = "bán thời gian" if i.mode == "part_time" else "toàn thời gian"
    upcoming = [m for m in i.milestones if m.status not in ("accepted",)]
    if upcoming:
        m = min(upcoming, key=lambda x: x.due_date)
        ctx["Mốc kế tiếp"] = f"{m.name} — hạn {m.due_date:%d/%m/%Y} ({m.status})"
    return ctx


def _open_conversation(db: Session, user: User, conversation_id: int | None) -> Conversation:
    if conversation_id:
        conv = db.get(Conversation, conversation_id)
        if conv is None or conv.user_id != user.id:
            raise HTTPException(status_code=404, detail="Không tìm thấy hội thoại")
        return conv
    conv = Conversation(user_id=user.id)
    db.add(conv)
    db.flush()
    return conv


def _ask_kwargs(db: Session, user: User) -> dict:
    return {
        "today": date.today(), "student_code": user.student_code,
        "known_pii": {"HO_TEN": user.full_name, "MSSV": user.student_code, "EMAIL": user.email, "SDT": user.phone},
        "user_context": _student_context(db, user),
    }


@router.post("/assistant/chat")
async def chat(body: ChatIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    ratelimit.enforce_usage(user.id, "assistant", get_settings().assistant_per_minute)
    conv = _open_conversation(db, user, body.conversation_id)
    db.add(Message(conversation_id=conv.id, role="user", content=body.message))
    result = await answer_policy_question(db, body.message, **_ask_kwargs(db, user))
    return _persist_answer(db, user, conv, result)


@router.post("/assistant/chat/stream")
async def chat_stream(body: ChatIn, user: User = Depends(current_user)) -> StreamingResponse:
    """SSE (NFR-1): `stage` khi xong từng bước, `delta` từng đoạn câu trả lời đã kiểm chứng, `done` cuối."""
    ratelimit.enforce_usage(user.id, "assistant", get_settings().assistant_per_minute)
    db = session_factory()()
    try:
        conv = _open_conversation(db, user, body.conversation_id)
    except HTTPException:
        db.close()
        raise

    async def events():
        try:
            db.add(Message(conversation_id=conv.id, role="user", content=body.message))
            async for event in stream_policy_answer(db, body.message, **_ask_kwargs(db, user)):
                if event["type"] == "final":
                    event = {"type": "done", **_persist_answer(db, user, conv, event["state"])}
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:  # lỗi giữa chừng → báo tường minh cho client, không im lặng
            db.rollback()
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)}, ensure_ascii=False)}\n\n"
        finally:
            db.close()

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _persist_answer(db: Session, user: User, conv: Conversation, result: dict) -> dict:
    outcome = result.get("outcome") or "not_found"
    if outcome == "refused":
        audit.record(db, actor_of(user), "assistant", conv.id, "refused", reason=result.get("violation_type", ""))
    reply = Message(conversation_id=conv.id, role="assistant", content=result["answer"],
                    meta={"outcome": outcome, "mode": result.get("mode", ""),
                          "decision_request": bool(result.get("decision_request"))})
    db.add(reply)
    db.flush()
    for c in result.get("citations", []):
        db.add(Citation(message_id=reply.id, chunk_id=c["chunk_id"], label=c["label"]))
    db.commit()
    return {
        "conversation_id": conv.id, "message_id": reply.id, "answer": result["answer"],
        "citations": result.get("citations", []), "outcome": outcome, "mode": result.get("mode", ""),
        "suggest_extension": bool(result.get("decision_request")) and user.role == "student",
    }


@router.get("/assistant/conversations/{conversation_id}")
def conversation(conversation_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="Không tìm thấy hội thoại")
    return {"id": conv.id, "messages": [
        {"role": m.role, "content": m.content, "meta": m.meta,
         "citations": [{"chunk_id": c.chunk_id, "label": c.label} for c in m.citations]}
        for m in conv.messages
    ]}


# ---------------------------------------------------------------- kho quy định (R9)

@router.get("/policies")
def list_policies(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    return [policy_out(p) for p in db.scalars(select(PolicyDoc).order_by(PolicyDoc.id.desc())).all()]


@router.get("/policies/{policy_id}")
def get_policy(policy_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    p = db.get(PolicyDoc, policy_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy văn bản")
    return {**policy_out(p), "chunks": [{"id": c.id, "path": c.path, "text": c.text} for c in p.chunks]}


@router.post("/policies/reindex")
def reindex_policies(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Tạo vector cho mọi đoạn còn thiếu (vd vừa thêm API key sau khi đã seed)."""
    if not can_manage_policies(user):
        raise HTTPException(status_code=403, detail="Bạn không có quyền quản lý kho văn bản quy định")
    if policy_index.get_embedder() is None:
        raise HTTPException(status_code=409, detail="Chưa cấu hình embedding (cần OPENAI_API_KEY)")
    missing = list(db.scalars(select(PolicyChunk).where(PolicyChunk.embedding.is_(None))).all())
    try:
        done = policy_index.embed_chunks(missing, raise_on_error=True)
    except policy_index.EmbeddingError as exc:
        raise HTTPException(status_code=502, detail=f"Nhà cung cấp embedding lỗi: {exc}") from exc
    audit.record(db, actor_of(user), "policy_doc", None, "reindex_embeddings", after={"chunks": done})
    db.commit()
    return {"embedded": done, "missing_before": len(missing)}


@router.post("/policies", status_code=201)
async def upload_policy(
    file: UploadFile = File(...),
    code: str = Form(..., min_length=2, max_length=64),
    title: str = Form(..., min_length=3, max_length=256),
    effective_from: date = Form(...),
    effective_to: date | None = Form(default=None),
    issuer: str = Form(default=""),
    supersedes_code: str | None = Form(default=None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    if not can_manage_policies(user):
        raise HTTPException(status_code=403, detail="Bạn không có quyền quản lý kho văn bản quy định")
    content = await file.read()
    try:
        text = extract_text(file.filename or "upload", content)
        doc = policy_index.ingest(
            db, code=code.strip(), title=title.strip(), text=text, effective_from=effective_from,
            effective_to=effective_to, issuer=issuer.strip(), supersedes_code=(supersedes_code or "").strip() or None,
            filename=file.filename or "", uploaded_by=user.id,
        )
    except (UnreadableDocument, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    audit.record(db, actor_of(user), "policy_doc", doc.id, "uploaded",
                 after={"code": doc.code, "supersedes_id": doc.supersedes_id, "chunks": len(doc.chunks)})
    db.commit()
    return policy_out(doc)
