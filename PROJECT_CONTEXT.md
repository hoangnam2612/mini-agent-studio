# PROJECT_CONTEXT.md (C5)

> Inspire team 001 (Memio) — Quick Rehydrate + Current Invariants.
> Đây là file agent đọc ĐẦU TIÊN khi resume session. Giữ < 60 giây để đọc.

## 0. Quick Rehydrate (≤ 60s)

- **Project**: VIN-15 — Hệ thống hỗ trợ thực tập bằng AI: cổng Sinh viên – Giảng viên (+ Quản trị viên tùy chọn), trợ lý chính sách có trích dẫn, giám sát mốc theo luật, phê duyệt HITL.
- **Spec / PRD**: `.kiro/specs/internship-ai-assistant/` (requirements, design, tasks, use-cases) · `PRD.md` (trạng thái từng yêu cầu theo code).
- **Stack**: Python 3.12 / FastAPI / LangGraph / SQLAlchemy (SQLite dev-test, Postgres compose) / SPA JS thuần trong `web/`.
- **Dev**: `docker compose up --build` → https://localhost (Caddy TLS) · API trực tiếp http://127.0.0.1:8000/docs. Không Docker: `uvicorn src.main:app --reload`.
- **Test**: `pytest` (124 test) · UI: `cd tests/ui && npm i && npm run smoke && npm run mobile` (cần server đang chạy, DB seed mới).
- **Env**: copy `.env.example` → `.env`. Không có `OPENAI_API_KEY` thì mọi tính năng AI chạy chế độ xác định (trích đoạn quy định, regex).

## 0.1 Current Invariants (để không drift)

- **Source of truth kỹ thuật**: code trong `src/`. File `.md` chỉ tóm tắt — khi mâu thuẫn,
  **CODE WINS**. Inspire team 011 source-of-truth rule.
- **Agent flow**: `src/agents/graph.py` (ReAct template, endpoint `/api/v1/chat` cũ) và `src/agents/policy_graph.py` (VIN-15: guard → retrieve → synthesize → verify → finalize).
- **HITL**: mọi đổi trạng thái đi qua `src/workflow/state_machine.py::transition()`; cạnh quyết định chỉ cho GV phụ trách là người thật.
- **Prompts**: `prompts/*.md` (external, `{{placeholder}}`).
- **Safety**: DANGER_KEYWORDS ở `nodes/safety_node.py` (cập nhật theo domain app).

## 0.2 Known Ambiguities / Mismatches (inspire team 011)

Liệt kê chỗ doc-vs-code lệch để agent không tin doc stale:
- [team điền khi phát hiện mismatch, vd: "PRD nói dùng Gemini nhưng code đang OpenAI"]

## 1. Quyết định kỹ thuật (link ADR)

Xem `WORKLOG.md` mục ADR. Mỗi quyết định lớn ghi theo format:
`[ADR-XXX] Context / Options / Decision / Consequences` (inspire team 010).

## 2. Cập nhật file này

Khi đổi stack/invariant → UPDATE FILE NÀY TRƯỚC, rồi mới sửa code. File này là contract
giữa các session agent.
