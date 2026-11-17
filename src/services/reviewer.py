"""Reviewer Summarizer (R3.2, R12.2) — gợi ý cho GV, KHÔNG ảnh hưởng quyết định.

- "CĐR chưa nhắc tới" tính xác định bằng từ khóa (không cần LLM, giải thích được).
- Tóm tắt: LLM nếu có (văn bản đã che PII), không thì trích câu đầu.
- Mọi kết quả gắn nhãn "Gợi ý của AI"; AI lỗi → trả None, UI ẩn phần gợi ý.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import date

from sqlalchemy.orm import Session

from src.agents.prompts import load_prompt
from src.config import get_settings
from src.models.orm import Cohort, ExtensionRequest
from src.services.llm import get_llm, llm_available
from src.services.pii import Redactor
from src.services.policy_index import normalize, search_policy

logger = logging.getLogger("vin15.reviewer")

AI_LABEL = "Gợi ý của AI — chỉ để tham khảo, GV là người quyết định"


def uncovered_outcomes(text: str, outcomes: list[dict]) -> list[dict]:
    plain = normalize(text)
    missing = []
    for outcome in outcomes:
        keywords = [normalize(k) for k in outcome.get("keywords", [])]
        if not any(re.search(rf"\b{re.escape(k)}\b", plain) for k in keywords):
            missing.append({"code": outcome["code"], "text": outcome["text"]})
    return missing


def _first_sentences(text: str, n: int = 2) -> str:
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return " ".join(s for s in sentences[:n] if s).strip()[:400]


def _llm_summary(text: str, purpose: str) -> str:
    # Hướng dẫn ở system, văn bản ở human — model nhỏ hay chép lại hướng dẫn nếu gộp chung
    system = load_prompt("reviewer_summary.md").replace("{{purpose}}", purpose)
    def call():
        return get_llm("classify").invoke([("system", system), ("human", text[:6000])])

    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(call)
    try:
        out = str(future.result(timeout=get_settings().reviewer_summary_budget_seconds).content).strip()
    except FutureTimeout as exc:
        future.cancel()
        raise TimeoutError("Tóm tắt đề cương vượt ngân sách thời gian") from exc
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    # Bỏ dòng model lặp lại hướng dẫn ("Tối đa 3 câu…") nếu có
    lines = [ln for ln in out.splitlines() if not re.search(r"(?i)tối đa \d+ câu|không đưa ra khuyến nghị", ln)]
    return "\n".join(lines).strip() or out


def summarize_outline(content: str, cohort: Cohort, redactor: Redactor) -> dict | None:
    try:
        summary = _llm_summary(redactor.redact(content), "đề cương thực tập") if llm_available() else _first_sentences(content)
        return {
            "label": AI_LABEL,
            "summary": summary,
            "uncovered_outcomes": uncovered_outcomes(content, cohort.outcomes or []),
            "source": "llm" if llm_available() else "rules",
        }
    except Exception as exc:  # R3.2: AI lỗi → GV vẫn duyệt bình thường
        logger.error("FAILED summarize_outline: %s", exc)
        return None


def summarize_extension(db: Session, request: ExtensionRequest, redactor: Redactor, today: date) -> dict | None:
    try:
        m = request.milestone
        days = (request.requested_due_date - request.previous_due_date).days
        # Truy vấn cố định theo chủ đề gia hạn — tên mốc làm nhiễu xếp hạng (kéo về Điều quy định mốc)
        hits = search_policy(db, "đề nghị gia hạn thời hạn nộp mốc lý do chính đáng", today, top_k=2)
        summary = (
            f"Xin dời hạn mốc '{m.name}' từ {request.previous_due_date:%d/%m/%Y} sang "
            f"{request.requested_due_date:%d/%m/%Y} (+{days} ngày). Lý do: {_first_sentences(request.reason, 1)}"
        )
        if llm_available():
            summary = _llm_summary(redactor.redact(summary + "\n" + request.reason), "yêu cầu gia hạn mốc")
        return {
            "label": AI_LABEL,
            "summary": summary,
            "extra_days": days,
            "related_clauses": [{"label": h.label, "text": h.text[:500], "chunk_id": h.chunk_id} for h in hits],
            "source": "llm" if llm_available() else "rules",
        }
    except Exception as exc:
        logger.error("FAILED summarize_extension: %s", exc)
        return None
