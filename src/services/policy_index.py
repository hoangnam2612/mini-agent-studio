"""Kho văn bản quy định: tách Điều/Khoản, lọc hiệu lực, tìm kiếm BM25 (R8.1, R9).

Truy hồi lai: BM25 thuần Python (giữ dấu; bỏ dấu khi câu hỏi gõ không dấu) + cosine trên
embedding khi có embedder (API key). Vector lưu JSON trong `policy_chunk.embedding` và so
trong RAM — chưa dùng pgvector (kho quy định chỉ vài trăm đoạn). Bộ lọc hiệu lực (P3) nằm trong
`search_policy` và do server áp, tham số từ LLM không thể nới ra.
"""

from __future__ import annotations

import logging
import math
import re
import unicodedata
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from src.config import get_settings
from src.models.orm import PolicyChunk, PolicyDoc
from src.services.llm import llm_available, openai_base_url

logger = logging.getLogger("vin15.policy_index")

_CHAPTER = re.compile(r"^\s*(?:#+\s*)?(Chương|CHƯƠNG)\s+([IVXLC\d]+)\b.*$")
_ARTICLE = re.compile(r"^\s*(?:#+\s*)?(?:\*\*)?Điều\s+(\d+)\s*[.:]?(.*)$")
_CLAUSE = re.compile(r"^\s*(\d+)\.\s+(.*)$")

_STOPWORDS = {
    "la", "va", "cua", "cho", "co", "duoc", "khong", "nhung", "cac", "mot", "trong", "voi", "thi", "de",
    "em", "toi", "minh", "ban", "nao", "gi", "the", "nay", "do", "khi", "neu", "hay", "phai", "bao",
    "nhieu", "lam", "sao", "tu", "den", "ve", "theo", "can", "nhu", "vay", "thay", "ah", "oi",
    "do", "da", "se", "vi", "boi", "ma", "ra", "vao", "con", "rat", "cung", "hon",
}


def normalize(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn").lower()


def tokenize(text: str, keep_accents: bool = True) -> list[str]:
    """Giữ dấu mặc định: bỏ dấu làm trùng nhiều từ ("dữ"/"du", "họa"/"hoa") → truy hồi sai.
    Chỉ bỏ dấu khi câu hỏi được gõ không dấu."""
    words = re.findall(r"\w+", unicodedata.normalize("NFC", text.lower()))
    out = []
    for w in words:
        plain = normalize(w)
        if plain in _STOPWORDS or len(plain) < 2:
            continue
        out.append(w if keep_accents else plain)
    return out


def has_accents(text: str) -> bool:
    return normalize(text) != text.lower()


@dataclass
class ChunkDraft:
    path: str
    text: str


def chunk_document(text: str) -> list[ChunkDraft]:
    """Tách theo Chương → Điều → Khoản. Điều không có khoản thì cả Điều là 1 chunk."""
    chapter = ""
    article = ""
    article_title = ""
    clause = ""
    buffer: list[str] = []
    chunks: list[ChunkDraft] = []

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if article and body:
            parts = [p for p in (chapter, f"Điều {article}", f"Khoản {clause}" if clause else "") if p]
            heading = f"Điều {article}. {article_title}".strip()
            chunks.append(ChunkDraft(" / ".join(parts), f"{heading}\n{body}"))
        buffer.clear()

    for raw in text.splitlines():
        line = raw.strip().strip("*").strip()
        if not line:
            continue
        if m := _CHAPTER.match(line):
            flush()
            chapter, article, clause = f"Chương {m.group(2)}", "", ""
            continue
        if m := _ARTICLE.match(line):
            flush()
            article, article_title, clause = m.group(1), m.group(2).strip(" .:*"), ""
            continue
        if article and (m := _CLAUSE.match(line)):
            flush()
            clause = m.group(1)
            buffer.append(line)
            continue
        if article:
            buffer.append(line)
    flush()
    return chunks


def ingest(
    db: Session,
    *,
    code: str,
    title: str,
    text: str,
    effective_from: date,
    effective_to: date | None = None,
    issuer: str = "",
    supersedes_code: str | None = None,
    filename: str = "",
    uploaded_by: int | None = None,
) -> PolicyDoc:
    chunks = chunk_document(text)
    if not chunks:
        raise ValueError("Không tách được Điều/Khoản nào — văn bản cần có dòng 'Điều N.'")
    doc = PolicyDoc(
        code=code, title=title, issuer=issuer, effective_from=effective_from, effective_to=effective_to,
        filename=filename, uploaded_by=uploaded_by,
    )
    if supersedes_code:
        old_docs = db.scalars(
            select(PolicyDoc).where(PolicyDoc.code == supersedes_code, PolicyDoc.status == "active")
        ).all()
        if not old_docs:
            raise ValueError(f"Không tìm thấy văn bản đang hiệu lực mã {supersedes_code} để thay thế")
        for old in old_docs:
            old.status = "superseded"  # R9.3 — giữ lại để tra cứu, không còn được truy hồi
            if old.effective_to is None or old.effective_to > effective_from:
                old.effective_to = effective_from
        doc.supersedes_id = old_docs[0].id
    doc.chunks = [PolicyChunk(ordinal=n, path=c.path, text=c.text) for n, c in enumerate(chunks)]
    embed_chunks(doc.chunks)
    db.add(doc)
    db.flush()
    return doc


# ---------------------------------------------------------------- embedding (R9.2)

Embedder = Callable[[list[str]], list[list[float]]]
_embedder_override: Embedder | None = None


def set_embedder(fn: Embedder | None) -> None:
    """Test cài embedder giả; None = trở về mặc định (OpenAI khi có key, không thì không có)."""
    global _embedder_override
    _embedder_override = fn


def get_embedder() -> Embedder | None:
    if _embedder_override is not None:
        return _embedder_override
    if not llm_available():
        return None
    from langchain_openai import OpenAIEmbeddings

    settings = get_settings()
    return OpenAIEmbeddings(
        model=settings.embedding_model, api_key=settings.openai_api_key,
        base_url=openai_base_url(),
        # Endpoint không phải OpenAI (Ollama…) không hiểu token id của tiktoken → gửi text thô
        check_embedding_ctx_length=not settings.openai_base_url,
    ).embed_documents


# Ngưỡng cosine đo trên kho quy định mẫu (8 câu đúng chủ đề / lạc đề, 2026-11-14):
#   text-embedding-3-small: đúng chủ đề 0.456–0.60, lạc đề ≤ 0.257 → 0.38
#   bge-m3:                 đúng chủ đề 0.61–0.67,  lạc đề ≤ 0.32  → 0.50
# nomic-embed-text không tách được tiếng Việt (lạc đề 0.76 > đúng chủ đề 0.65) → không có ngưỡng.
CALIBRATED_SIMILARITY = {"text-embedding-3-small": 0.38, "bge-m3": 0.50}
DEFAULT_SIMILARITY = 0.5  # model chưa hiệu chỉnh — đo lại trước khi dùng


def min_similarity() -> float:
    settings = get_settings()
    if settings.embedding_min_similarity is not None:
        return settings.embedding_min_similarity
    return CALIBRATED_SIMILARITY.get(settings.embedding_model, DEFAULT_SIMILARITY)


class EmbeddingError(Exception):
    pass


def embed_chunks(chunks: list[PolicyChunk], raise_on_error: bool = False) -> int:
    """Gắn vector cho chunk. Lỗi embedder → giữ None, truy hồi vẫn chạy bằng BM25.

    raise_on_error=True (endpoint reindex): báo lỗi nhà cung cấp cho người gọi thay vì nuốt im lặng.
    """
    embedder = get_embedder()
    if embedder is None or not chunks:
        return 0
    try:
        vectors = embedder([c.path + "\n" + c.text for c in chunks])
    except Exception as exc:
        logger.error("FAILED embed_chunks: %s", exc)
        if raise_on_error:
            raise EmbeddingError(str(exc)[:300]) from exc
        return 0
    for chunk, vec in zip(chunks, vectors, strict=True):
        chunk.embedding = [float(x) for x in vec]
    return len(chunks)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


@dataclass
class Hit:
    chunk_id: int
    doc_code: str
    doc_title: str
    path: str
    text: str
    effective_from: date
    score: float
    lexical: bool = True  # qua ngưỡng từ khóa (False = chỉ qua ngưỡng embedding)

    @property
    def label(self) -> str:
        return f"{self.doc_code} · {self.path} · hiệu lực {self.effective_from:%d/%m/%Y}"


def active_chunks(db: Session, today: date) -> list[PolicyChunk]:
    """Chỉ chunk của văn bản `active` và đang trong thời hạn hiệu lực (P3)."""
    stmt = (
        select(PolicyChunk)
        .join(PolicyDoc)
        .where(
            PolicyDoc.status == "active",
            PolicyDoc.effective_from <= today,
            or_(PolicyDoc.effective_to.is_(None), PolicyDoc.effective_to > today),
        )
        .options(selectinload(PolicyChunk.doc))
    )
    return list(db.scalars(stmt).all())


def search_policy(db: Session, query: str, today: date, top_k: int | None = None) -> list[Hit]:
    settings = get_settings()
    top_k = top_k or settings.retrieval_top_k
    chunks = active_chunks(db, today)
    accents = has_accents(query)
    q_tokens = tokenize(query, keep_accents=accents)
    q_terms = set(q_tokens)
    q_bigrams = set(zip(q_tokens, q_tokens[1:], strict=False))
    if not chunks or not q_terms:
        return []
    # Vector câu hỏi — chỉ khi có embedder và kho đã có vector
    q_vec: list[float] | None = None
    embedder = get_embedder()
    if embedder is not None and any(c.embedding for c in chunks):
        try:
            q_vec = embedder([query])[0]
        except Exception as exc:
            logger.error("FAILED embed query: %s", exc)
    docs = [tokenize(c.path + " " + c.text, keep_accents=accents) for c in chunks]
    avg_len = sum(len(d) for d in docs) / len(docs)
    df = Counter(t for d in docs for t in set(d))
    n = len(docs)
    k1, b = 1.5, 0.75
    # Đoạn phải chứa đủ tỉ lệ từ khóa của câu hỏi — chặn trường hợp 1 từ phổ biến ("hành", "gia")
    # kéo một đoạn không liên quan vượt ngưỡng điểm (R8.5: không đủ căn cứ thì không trả lời).
    min_matched = max(1, math.ceil(settings.retrieval_min_coverage * len(q_terms)))
    hits = []
    for chunk, terms in zip(chunks, docs, strict=True):
        tf = Counter(terms)
        similarity = _cosine(q_vec, chunk.embedding) if q_vec and chunk.embedding else 0.0
        semantic_ok = similarity >= min_similarity()
        lexical_ok = sum(1 for t in q_terms if t in tf) >= min_matched
        if not (lexical_ok or semantic_ok):
            continue
        score = 0.0
        for t in q_terms:
            if t not in tf:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            score += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(terms) / avg_len))
        if score > 0 and q_bigrams:
            # Cụm 2 từ khớp liền nhau ("thoi gian", "toi thieu") — ưu tiên đoạn nói đúng cụm hỏi
            score += 2.0 * len(q_bigrams & set(zip(terms, terms[1:], strict=False)))
        lexical_pass = lexical_ok and score >= settings.retrieval_min_score
        if semantic_ok:
            # Đồng nghĩa ("hạn chót" ~ "thời hạn") — đoạn qua ngưỡng tương đồng được giữ dù ít từ chung
            score += settings.embedding_weight * similarity
        if lexical_pass or semantic_ok:
            hits.append(Hit(chunk.id, chunk.doc.code, chunk.doc.title, chunk.path, chunk.text,
                            chunk.doc.effective_from, round(score, 3), lexical_pass))
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:top_k]
