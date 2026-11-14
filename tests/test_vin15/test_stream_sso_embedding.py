"""Streaming SSE + độ trễ (NFR-1), SSO/OIDC (R1.2), embedding (R9.2)."""

from __future__ import annotations

import json
import time
from datetime import date
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from sqlalchemy import select

from src.config import get_settings
from src.core import oidc
from src.models.orm import PolicyChunk
from src.services import policy_index

TODAY = date.today()


def _events(raw: str) -> list[dict]:
    return [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]


# ---------------------------------------------------------------- streaming (NFR-1)

async def test_stream_emits_stages_then_verified_answer(api):
    headers = await api.login("sv03")
    async with api.client.stream("POST", "/api/v1/assistant/chat/stream", headers=headers,
                                 json={"message": "Báo cáo cuối kỳ nộp khi nào?"}) as r:
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
        raw = "".join([chunk async for chunk in r.aiter_text()])
    events = _events(raw)
    stages = [e["stage"] for e in events if e["type"] == "stage"]
    assert stages == ["guard", "retrieve", "synthesize", "verify", "finalize"]
    done = events[-1]
    assert done["type"] == "done" and done["outcome"] == "answered" and done["citations"]
    assert "".join(e["text"] for e in events if e["type"] == "delta") == done["answer"]
    conv = (await api.call("GET", f"/assistant/conversations/{done['conversation_id']}", "sv03")).json()
    assert conv["messages"][1]["content"] == done["answer"]


async def test_stream_refusal_and_auth(api):
    headers = await api.login("sv03")
    r = await api.client.post("/api/v1/assistant/chat/stream", headers=headers,
                              json={"message": "Cho em xem hồ sơ của SV2026010"})
    events = _events(r.text)
    assert [e["stage"] for e in events if e["type"] == "stage"] == ["guard", "finalize"]
    assert events[-1]["outcome"] == "refused"
    assert (await api.client.post("/api/v1/assistant/chat/stream", json={"message": "x"})).status_code == 401


async def test_nfr1_latency_no_llm_mode(api):
    """NFR-1: p95 ≤ 10 s cho câu trả lời đầy đủ, sự kiện đầu ≤ 2 s (chế độ không LLM, SQLite)."""
    headers = await api.login("sv03")
    questions = ["Thời gian thực tập tối thiểu là bao nhiêu tuần?", "Khi nào phải nộp đề cương?",
                 "Mỗi tuần cần bao nhiêu giờ?", "Em có được gia hạn nộp báo cáo không?", "Giá vàng hôm nay?"]
    totals, firsts = [], []
    for n in range(30):
        start = time.perf_counter()
        first = None
        async with api.client.stream("POST", "/api/v1/assistant/chat/stream", headers=headers,
                                     json={"message": questions[n % len(questions)]}) as r:
            async for _ in r.aiter_text():
                first = first or time.perf_counter() - start
        totals.append(time.perf_counter() - start)
        firsts.append(first)
    p95 = sorted(totals)[int(0.95 * len(totals)) - 1]
    print(f"\nNFR-1 no-LLM: p95 total={p95 * 1000:.0f} ms, max first-event={max(firsts) * 1000:.0f} ms")
    assert p95 <= 10 and max(firsts) <= 2


# ---------------------------------------------------------------- SSO/OIDC (R1.2)

ISSUER = "https://idp.test/realms/school"


@pytest.fixture
def idp(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "oidc_issuer", ISSUER)
    monkeypatch.setattr(s, "oidc_client_id", "vin15")
    monkeypatch.setattr(s, "oidc_client_secret", "secret")
    oidc._discovery_cache.clear()
    userinfo = {"sub": "abc-123", "email": "sv03@student.demo.edu.vn", "email_verified": True}
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(200, json={
                "authorization_endpoint": f"{ISSUER}/auth", "token_endpoint": f"{ISSUER}/token",
                "userinfo_endpoint": f"{ISSUER}/userinfo"})
        if request.url.path.endswith("/token"):
            seen["token_form"] = parse_qs(request.content.decode())
            ok = seen["token_form"]["code"] == ["good-code"]
            return httpx.Response(200 if ok else 400, json={"access_token": "at-1"} if ok else {"error": "invalid_grant"})
        if request.url.path.endswith("/userinfo"):
            assert request.headers["Authorization"] == "Bearer at-1"
            return httpx.Response(200, json=userinfo)
        return httpx.Response(404)

    monkeypatch.setattr(oidc, "http_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    yield {"userinfo": userinfo, "seen": seen}
    oidc._discovery_cache.clear()


async def _login_redirect(api) -> str:
    r = await api.client.get("/api/v1/auth/oidc/login")
    assert r.status_code == 302 and r.headers["location"].startswith(f"{ISSUER}/auth?")
    params = parse_qs(urlparse(r.headers["location"]).query)
    assert params["client_id"] == ["vin15"] and params["response_type"] == ["code"]
    return params["state"][0]


async def test_sso_login_maps_to_local_account(api, idp):
    assert (await api.client.get("/api/v1/auth/oidc/config")).json() == {"enabled": True}
    state = await _login_redirect(api)
    r = await api.client.get("/api/v1/auth/oidc/callback", params={"code": "good-code", "state": state})
    assert r.status_code == 302 and r.headers["location"].startswith("/#/sso/")
    assert idp["seen"]["token_form"]["client_secret"] == ["secret"]
    token = r.headers["location"].removeprefix("/#/sso/")
    me = (await api.client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})).json()
    assert me["username"] == "sv03" and me["role"] == "student"


@pytest.mark.parametrize("case", ["bad_state", "bad_code", "unknown_user", "idp_error"])
async def test_sso_failures_redirect_with_error(api, idp, case):
    state = await _login_redirect(api)
    params = {"code": "good-code", "state": state}
    if case == "bad_state":
        params["state"] = state[:-2] + "xx"
    elif case == "bad_code":
        params["code"] = "stolen"
    elif case == "unknown_user":
        idp["userinfo"]["email"] = "outsider@gmail.com"
    else:
        params = {"error": "access_denied"}
    r = await api.client.get("/api/v1/auth/oidc/callback", params=params)
    assert r.status_code == 302 and r.headers["location"].startswith("/#/sso-error/")


async def test_sso_disabled_by_default(api):
    assert (await api.client.get("/api/v1/auth/oidc/config")).json() == {"enabled": False}
    assert (await api.client.get("/api/v1/auth/oidc/login")).status_code == 404


# ---------------------------------------------------------------- embedding (R9.2)

_CONCEPTS = [("deadline", "hạn", "chậm nhất"), ("report", "báo cáo"), ("cuối",)]


def fake_embedder(texts: list[str]) -> list[list[float]]:
    out = []
    for t in texts:
        low = t.lower()
        out.append([1.0 if any(w in low for w in group) else 0.0 for group in _CONCEPTS] + [0.1])
    return out


@pytest.fixture
def embedder():
    policy_index.set_embedder(fake_embedder)
    yield
    policy_index.set_embedder(None)


def test_synonym_query_needs_embeddings(db, embedder):
    query = "deadline của report cuối"
    policy_index.set_embedder(None)
    assert policy_index.search_policy(db, query, TODAY) == []  # BM25 không hiểu "deadline", "report"
    policy_index.set_embedder(fake_embedder)
    chunks = list(db.scalars(select(PolicyChunk)).all())
    assert policy_index.embed_chunks(chunks) == len(chunks)
    db.flush()
    hits = policy_index.search_policy(db, query, TODAY)
    assert hits and "báo cáo cuối kỳ chậm nhất" in hits[0].text
    assert all(h.doc_code != "QĐ-TT/2025" for h in hits)  # vẫn chỉ văn bản hiệu lực (P3)


def test_ingest_embeds_new_documents(db, embedder):
    doc = policy_index.ingest(db, code="HD-X", title="Hướng dẫn X", effective_from=TODAY,
                              text="Điều 1. Nộp báo cáo\n1. Hạn nộp báo cáo là thứ Sáu.")
    assert all(c.embedding for c in doc.chunks)


async def test_reindex_endpoint(api, embedder):
    r = await api.call("POST", "/policies/reindex", "admin")
    assert r.status_code == 200 and r.json()["embedded"] == r.json()["missing_before"] > 0
    assert (await api.call("POST", "/policies/reindex", "gv02")).status_code == 403


def test_empty_base_url_env_does_not_break_openai_clients(monkeypatch):
    """Hồi quy: `.env` có `OPENAI_BASE_URL=` rỗng → SDK đọc chuỗi rỗng → 'URL is missing a protocol'."""
    from src.services.llm import get_llm

    monkeypatch.setenv("OPENAI_BASE_URL", "")
    monkeypatch.setattr(get_settings(), "openai_api_key", "sk-test-not-real")
    monkeypatch.setattr(get_settings(), "openai_base_url", "")
    embedder = policy_index.get_embedder()
    assert str(embedder.__self__.client._client.base_url).startswith("https://api.openai.com/v1")
    assert str(get_llm("generate").root_client.base_url).startswith("https://api.openai.com/v1")


async def test_reindex_reports_provider_error(api):
    def broken(texts):
        raise RuntimeError("Error code: 401 - Your API key has expired")

    policy_index.set_embedder(broken)
    try:
        r = await api.call("POST", "/policies/reindex", "admin")
        assert r.status_code == 502 and "expired" in r.json()["detail"]
    finally:
        policy_index.set_embedder(None)


async def test_reindex_without_embedder(api):
    assert (await api.call("POST", "/policies/reindex", "admin")).status_code == 409


def test_similarity_threshold_is_calibrated_per_model(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "embedding_min_similarity", None)
    monkeypatch.setattr(s, "embedding_model", "text-embedding-3-small")
    assert policy_index.min_similarity() == 0.38
    monkeypatch.setattr(s, "embedding_model", "bge-m3")
    assert policy_index.min_similarity() == 0.50
    monkeypatch.setattr(s, "embedding_min_similarity", 0.7)  # ghi đè tường minh
    assert policy_index.min_similarity() == 0.7
    from src.config import Settings

    assert Settings(embedding_min_similarity="").embedding_min_similarity is None  # dòng .env để trống
