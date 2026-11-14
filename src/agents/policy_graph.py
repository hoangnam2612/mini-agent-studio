"""Policy Assistant (R8) — pipeline LangGraph: guard → retrieve → synthesize → verify → finalize.

Vì sao pipeline tuyến tính thay vì ReAct loop của template: trợ lý chỉ có MỘT
nguồn (kho quy định) và không có tool ghi, nên vòng ReAct không thêm giá trị
mà tăng độ trễ. Đây là "pattern pipeline" mà CLAUDE.md cho phép dùng cho RAG.

Bất biến:
- Bộ lọc hiệu lực do server áp trong `search_policy` (P3).
- Mọi câu giữ lại phải có marker [[chunk:id]] trỏ tới chunk truy hồi trong lượt (P2).
- Prompt gửi LLM chỉ chứa query đã che PII + ngữ cảnh tối thiểu (P6).
- Agent không có tool ghi trạng thái; "xin gia hạn" chỉ là gợi ý mở form (R8.6).
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable
from datetime import date
from typing import TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from src.agents.guardrails import GuardrailViolation, guardrails
from src.agents.policy_guard import check_policy_query
from src.agents.prompts import SHARED_RULES, load_prompt
from src.config import get_settings
from src.services.llm import get_llm, llm_available
from src.services.pii import Redactor
from src.services.policy_index import search_policy, tokenize

logger = logging.getLogger("vin15.policy")

MARKER = re.compile(r"\[\[chunk:(\d+)\]\]")
MAX_ATTEMPTS = 2

NOT_FOUND = (
    "Tôi không tìm thấy quy định nào đang có hiệu lực trả lời được câu hỏi này, nên không thể trả lời "
    "chắc chắn. Bạn hãy liên hệ giảng viên phụ trách để được hướng dẫn."
)
DECISION_NOTE = (
    "Lưu ý: trợ lý chỉ giải thích quy định, không thể duyệt hay cam kết kết quả. Nếu cần dời hạn một mốc, "
    "bạn hãy tạo yêu cầu gia hạn ở mục Mốc; giảng viên phụ trách sẽ xem xét và quyết định."
)
UNAVAILABLE = "Trợ lý tạm thời không trả lời được. Bạn hãy thử lại sau hoặc liên hệ giảng viên phụ trách."


class PolicyState(TypedDict, total=False):
    query: str
    student_code: str | None
    known_pii: dict
    user_context: dict
    today: str
    redacted_query: str
    refusal_reason: str
    violation_type: str
    decision_request: bool
    hits: list[dict]
    draft: str
    attempts: int
    feedback: str
    prompts_sent: list[str]
    answer: str
    citations: list[dict]
    outcome: str  # answered | not_found | refused | unavailable
    mode: str  # generated | extractive | extractive_fallback | extractive_timeout
    started_at: float
    timed_out: bool
    stage: str


SynthesizeFn = Callable[[PolicyState, str], Awaitable[str]]


def build_prompt(state: PolicyState) -> str:
    # Đánh số [1], [2]… — model nhỏ làm theo dạng này tốt hơn [[chunk:id]]; server đổi lại trước khi verify.
    # Chỉ gửi N đoạn đầu, mỗi đoạn tối đa M ký tự: prompt ngắn → độ trễ thấp (NFR-1), nhất là model chạy CPU.
    settings = get_settings()
    hits = state.get("hits", [])[: settings.llm_context_hits]
    context = "\n\n".join(
        f"[{n}] ({h['label']})\n{h['text'][: settings.llm_context_chars]}" for n, h in enumerate(hits, start=1)
    )
    profile = "\n".join(f"- {k}: {v}" for k, v in state.get("user_context", {}).items())
    return (
        load_prompt("policy_assistant.md")
        .replace("{{shared_rules}}", SHARED_RULES)
        .replace("{{student_context}}", profile or "(không có)")
        .replace("{{context}}", context)
        .replace("{{question}}", state.get("redacted_query", ""))
        .replace("{{feedback}}", state.get("feedback", ""))
    )


async def llm_synthesize(state: PolicyState, prompt: str) -> str:
    # Hướng dẫn + ngữ cảnh ở system, câu hỏi ở human — tránh model lặp lại hướng dẫn trong câu trả lời
    result = await get_llm("generate").ainvoke([("system", prompt), ("human", state.get("redacted_query", ""))])
    return str(result.content)


_NUMBERED = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def normalize_markers(draft: str, hits: list[dict]) -> str:
    """Đổi trích dẫn dạng [n] / [1, 2] thành [[chunk:id]]. Số ngoài danh sách → chunk:-1 (bị verify loại)."""
    def repl(match: re.Match) -> str:
        out = []
        for raw in match.group(1).split(","):
            n = int(raw)
            out.append(f"[[chunk:{hits[n - 1]['chunk_id']}]]" if 1 <= n <= len(hits) else "[[chunk:-1]]")
        return "".join(out)

    protected = MARKER.sub(lambda m: f"\x00{m.group(1)}\x00", draft)  # giữ nguyên marker [[chunk:id]] sẵn có
    return re.sub(r"\x00(\d+)\x00", r"[[chunk:\1]]", _NUMBERED.sub(repl, protected))


def extractive_answer(hits: list[dict]) -> str:
    return "\n".join(f"Theo {h['label']}: {_excerpt(h['text'])} [[chunk:{h['chunk_id']}]]" for h in hits[:2])


def _excerpt(text: str, limit: int = 320) -> str:
    body = text.split("\n", 1)[-1].strip()
    if len(body) <= limit:
        return body
    cut = body[:limit]
    end = max(cut.rfind(". "), cut.rfind("; "))
    return (cut[: end + 1] if end > 80 else cut.rstrip() + "…").strip()


async def extractive_synthesize(state: PolicyState, prompt: str) -> str:
    """Chế độ không có LLM: trích nguyên văn khoản liên quan nhất, mỗi đoạn một marker."""
    return extractive_answer(state.get("hits", []))


MIN_WORDS = 4  # câu quá ngắn ("Từ đoạn [1]") có trích dẫn nhưng không có nội dung → loại
MIN_SUPPORT = 0.6  # tỉ lệ từ nội dung của câu phải có trong đoạn được trích (bám nguồn)
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
_ANY_MARKER = re.compile(r"\s*\[\[chunk:(-?\d+)\]\]")


def _content_tokens(text: str) -> set[str]:
    # Từ có nghĩa (bỏ stopword) + mọi con số — số liệu sai là lỗi nặng nhất của trả lời quy định
    return set(tokenize(text, keep_accents=False)) | set(re.findall(r"\d+", text))


def support(sentence: str, source: str) -> float:
    tokens = _content_tokens(sentence)
    source_tokens = _content_tokens(source)
    # Số liệu phải có trong THÂN đoạn — bỏ tiêu đề "Điều N." và số thứ tự khoản "2." đầu dòng,
    # nếu không "2 tuần" sẽ khớp nhầm với số khoản "2." của đoạn ghi "8 tuần"
    body = re.sub(r"(?im)^\s*(?:điều\s+\d+\.?.*$|\d+\.\s)", " ", source)
    if set(re.findall(r"\d+", sentence)) - set(re.findall(r"\d+", body)):
        return 0.0  # số liệu không có trong nguồn → không bám nguồn
    return len(tokens & source_tokens) / len(tokens) if tokens else 0.0


def verify_citations(draft: str, sources: dict[int, str]) -> tuple[str, list[int]]:
    """Kiểm chứng từng câu (R8.4): chỉ trích chunk của lượt này, có nội dung, và BÁM NGUỒN.

    - Câu có marker: mọi id phải thuộc `sources` và câu phải đạt MIN_SUPPORT so với các đoạn được trích
      (chặn câu trả lời lạc đề gắn bừa [1]).
    - Câu không có marker: gắn vào đoạn nó bám nhiều nhất nếu đạt ngưỡng; không thì bỏ.
    """
    kept: list[str] = []
    used: list[int] = []
    for raw in _SENTENCE.split(draft):
        ids = [int(x) for x in _ANY_MARKER.findall(raw)]
        text = _ANY_MARKER.sub("", raw).strip().lstrip("-*•.!?;:) ").strip()
        punct = text[-1] if text and text[-1] in ".!?;:" else "."
        text = text.rstrip(".!?;: ")
        if len(text.split()) < MIN_WORDS:
            continue
        if ids:
            if not all(i in sources for i in ids):
                continue
            if support(text, " ".join(sources[i] for i in ids)) < MIN_SUPPORT:
                continue
        else:
            best = max(sources, key=lambda i: support(text, sources[i]), default=None)
            if best is None or support(text, sources[best]) < MIN_SUPPORT:
                continue
            ids = [best]
        kept.append(text + " " + "".join(f"[[chunk:{i}]]" for i in ids) + punct)
        used.extend(i for i in ids if i not in used)
    return "\n".join(kept), used


def make_policy_graph(db: Session, synthesize_fn: SynthesizeFn | None = None):
    synth = synthesize_fn or (llm_synthesize if llm_available() else extractive_synthesize)

    async def guard(state: PolicyState) -> dict:
        result = check_policy_query(state["query"], state.get("student_code"))
        if result.refusal_reason:
            logger.warning("policy guard refused [%s]", result.violation_type)
            return {"refusal_reason": result.refusal_reason, "violation_type": result.violation_type,
                    "outcome": "refused", "stage": "refusal"}
        redacted = Redactor(state.get("known_pii", {})).redact(state["query"])
        return {"decision_request": result.decision_request, "redacted_query": redacted, "stage": "guard"}

    async def retrieve(state: PolicyState) -> dict:
        today = date.fromisoformat(state["today"])
        hits = search_policy(db, state["redacted_query"], today)
        return {
            "hits": [{"chunk_id": h.chunk_id, "label": h.label, "text": h.text, "score": h.score,
                      "doc_code": h.doc_code, "path": h.path, "lexical": h.lexical} for h in hits],
            "attempts": 0, "started_at": time.monotonic(), "stage": "retrieve",
        }

    async def synthesize(state: PolicyState) -> dict:
        prompt = build_prompt(state)
        sent = list(state.get("prompts_sent", []))
        sent.append(prompt)
        budget = get_settings().llm_answer_budget_seconds
        remaining = budget - (time.monotonic() - state.get("started_at", time.monotonic())) if budget else None
        try:
            if remaining is not None and remaining <= 0:
                raise TimeoutError
            draft = await asyncio.wait_for(synth(state, prompt), timeout=remaining)
        except TimeoutError:
            # NFR-1: hết ngân sách thời gian → verify trả trích dẫn nguyên văn đã kiểm chứng
            logger.warning("policy synthesize hết ngân sách %.1fs", budget)
            return {"draft": "", "attempts": MAX_ATTEMPTS, "timed_out": True, "prompts_sent": sent, "stage": "synthesize"}
        except Exception as exc:
            logger.error("FAILED policy synthesize: %s", exc)
            return {"outcome": "unavailable", "prompts_sent": sent, "stage": "synthesize"}
        return {"draft": draft, "attempts": state.get("attempts", 0) + 1, "prompts_sent": sent, "stage": "synthesize"}

    async def verify(state: PolicyState) -> dict:
        hits = state.get("hits", [])
        # Đoạn đủ căn cứ để trích nguyên văn: mọi hit đã qua ngưỡng (từ khóa, hoặc embedding ≥
        # EMBEDDING_MIN_SIMILARITY). Ngưỡng embedding PHẢI được hiệu chỉnh theo model — với nomic-embed-text,
        # câu lạc đề vượt cả câu đúng chủ đề (xem deploy/docker-compose.llm.yml).
        lexical = hits
        if synth is extractive_synthesize:
            if not lexical:
                return {"draft": "", "attempts": MAX_ATTEMPTS, "stage": "verify"}
            return {"draft": extractive_answer(lexical), "outcome": "answered", "mode": "extractive", "stage": "verify"}
        if "KHONG_TIM_THAY" in state.get("draft", ""):
            return {"draft": "", "attempts": MAX_ATTEMPTS, "stage": "verify"}  # LLM tự nhận không có căn cứ
        shown = hits[: get_settings().llm_context_hits]  # chỉ các đoạn model thực sự được xem
        sources = {h["chunk_id"]: h["text"] for h in shown}
        cleaned, used = verify_citations(normalize_markers(state.get("draft", ""), shown), sources)
        if used:
            return {"draft": cleaned, "outcome": "answered", "mode": "generated", "stage": "verify"}
        if state.get("attempts", 0) >= MAX_ATTEMPTS and lexical:
            # Model không viết được câu bám nguồn, nhưng đã có đoạn khớp từ khóa đủ ngưỡng:
            # trích nguyên văn (luôn đúng nguồn) thay vì nói "không tìm thấy".
            mode = "extractive_timeout" if state.get("timed_out") else "extractive_fallback"
            return {"draft": extractive_answer(lexical), "outcome": "answered", "mode": mode, "stage": "verify"}
        return {
            "draft": "",
            "feedback": "Lần trước câu trả lời thiếu hoặc sai số trích dẫn. Mỗi câu PHẢI có nội dung và kết thúc bằng [n] của đoạn quy định đã cho.",
            "stage": "verify",
        }

    async def finalize(state: PolicyState) -> dict:
        outcome = state.get("outcome") or "not_found"
        if outcome == "refused":
            return {"answer": f"Tôi không thể xử lý yêu cầu này. {state['refusal_reason']}", "citations": [], "stage": "finalize"}
        if outcome == "unavailable":
            return {"answer": UNAVAILABLE, "citations": [], "stage": "finalize"}
        if outcome != "answered":
            answer = NOT_FOUND
            if state.get("decision_request"):
                answer += "\n\n" + DECISION_NOTE
            return {"answer": answer, "citations": [], "outcome": "not_found", "stage": "finalize"}

        by_id = {h["chunk_id"]: h for h in state["hits"]}
        order: list[int] = []
        for match in MARKER.finditer(state["draft"]):
            cid = int(match.group(1))
            if cid not in order:
                order.append(cid)
        answer = MARKER.sub(lambda m: f"[{order.index(int(m.group(1))) + 1}]", state["draft"])
        answer = re.sub(r"(\[\d+\])(\s*\1)+", r"\1", answer)
        if state.get("decision_request"):
            answer += "\n\n" + DECISION_NOTE
        try:
            guardrails.check_output_text(answer)
        except GuardrailViolation:
            return {"answer": UNAVAILABLE, "citations": [], "outcome": "unavailable", "stage": "finalize"}
        citations = [
            {"n": n + 1, "chunk_id": cid, "label": by_id[cid]["label"], "excerpt": _excerpt(by_id[cid]["text"], 500)}
            for n, cid in enumerate(order)
        ]
        return {"answer": answer, "citations": citations, "stage": "finalize"}

    def after_guard(state: PolicyState) -> str:
        return "finalize" if state.get("refusal_reason") else "retrieve"

    def after_retrieve(state: PolicyState) -> str:
        return "synthesize" if state.get("hits") else "finalize"

    def after_synthesize(state: PolicyState) -> str:
        return "finalize" if state.get("outcome") == "unavailable" else "verify"

    def after_verify(state: PolicyState) -> str:
        if state.get("outcome") == "answered" or state.get("attempts", 0) >= MAX_ATTEMPTS:
            return "finalize"
        return "synthesize"  # sinh lại đúng 1 lần (R8.4, design §6)

    graph = StateGraph(PolicyState)
    graph.add_node("guard", guard)
    graph.add_node("retrieve", retrieve)
    graph.add_node("synthesize", synthesize)
    graph.add_node("verify", verify)
    graph.add_node("finalize", finalize)
    graph.set_entry_point("guard")
    graph.add_conditional_edges("guard", after_guard, ["retrieve", "finalize"])
    graph.add_conditional_edges("retrieve", after_retrieve, ["synthesize", "finalize"])
    graph.add_conditional_edges("synthesize", after_synthesize, ["verify", "finalize"])
    graph.add_conditional_edges("verify", after_verify, ["synthesize", "finalize"])
    graph.add_edge("finalize", END)
    return graph.compile()


STAGE_LABELS = {
    "guard": "Kiểm tra câu hỏi",
    "retrieve": "Tra cứu văn bản đang hiệu lực",
    "synthesize": "Soạn câu trả lời",
    "verify": "Kiểm chứng trích dẫn",
    "finalize": "Hoàn tất",
}


async def stream_policy_answer(
    db: Session,
    query: str,
    *,
    today: date,
    student_code: str | None,
    known_pii: dict,
    user_context: dict,
    synthesize_fn: SynthesizeFn | None = None,
    chunk_words: int = 6,
):
    """Sinh sự kiện cho SSE (NFR-1): tiến độ từng bước → câu trả lời từng đoạn → kết quả cuối.

    Chỉ stream văn bản ĐÃ qua verify_citations — không đẩy bản nháp chưa kiểm chứng ra
    màn hình (giữ P2). Sự kiện đầu tiên đến ngay khi bước guard xong, trước khi gọi LLM.
    """
    graph = make_policy_graph(db, synthesize_fn)
    state: dict = {
        "query": query, "student_code": student_code, "known_pii": known_pii,
        "user_context": user_context, "today": today.isoformat(),
    }
    async for update in graph.astream(state, stream_mode="updates"):
        for node, delta in update.items():
            state.update(delta or {})
            yield {"type": "stage", "stage": node, "label": STAGE_LABELS.get(node, node)}
    words = state.get("answer", "").split(" ")
    for start in range(0, len(words), chunk_words):
        piece = " ".join(words[start:start + chunk_words])
        yield {"type": "delta", "text": piece + (" " if start + chunk_words < len(words) else "")}
    yield {"type": "final", "state": state}


async def answer_policy_question(
    db: Session,
    query: str,
    *,
    today: date,
    student_code: str | None,
    known_pii: dict,
    user_context: dict,
    synthesize_fn: SynthesizeFn | None = None,
) -> PolicyState:
    graph = make_policy_graph(db, synthesize_fn)
    return await graph.ainvoke({
        "query": query, "student_code": student_code, "known_pii": known_pii,
        "user_context": user_context, "today": today.isoformat(),
    })
