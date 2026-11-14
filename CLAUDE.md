# CLAUDE.md — Project context cho Claude Code (C4/C5)

> Inspire team 001 (PROJECT_CONTEXT Quick Rehydrate) + team 008 (CLAUDE.md structure).

## Quick Rehydrate (≤ 60s)

Đọc nhanh khi mất context:
- **Đây là**: AI20K Agent Template — starter code cho học viên VinUni build AI Agent.
- **Đề tài**: Hệ thống hỗ trợ thực tập bằng AI — xem `docs/problem-statement.md`.
- **Stack**: Python 3.12, FastAPI, LangGraph 1.x, LangChain 1.x, Pydantic v2.
- **Mock-first**: agent chạy được KHÔNG cần OPENAI_API_KEY (xem `src/services/llm.py`).
- **Chạy server**: `uvicorn src.main:app --reload` → http://localhost:8000/docs
- **Chạy test**: `pytest tests/ -v`
- **Chạy eval**: `python eval/run_eval.py`

## Current Invariants (để không drift)

- **Source of truth kỹ thuật**: code trong `src/`. File `.md` (kể cả file này) chỉ là
  tóm tắt — khi mâu thuẫn, CODE WINS (inspire team 011 source-of-truth rule).
- **Agent graph**: `src/agents/graph.py` — ReAct harness loop: guardrail → reason → act
  (tools, HITL interrupt cho risky tools) → assess → finalize (escape hatch max-iterations).
  Pattern pipeline thay thế: safety → retrieve → synthesize → validate (nodes/ còn lại,
  dùng khi cần RAG pipeline tuyến tính thay vì ReAct loop). Đừng thêm node mà không cập nhật state schema.
- **Prompts**: nằm ở `prompts/*.md` (external file, `{{placeholder}}`). KHÔNG nhúng
  prompt dài trong Python string.
- **Safety guardrail**: DANGER_KEYWORDS ở `nodes/safety_node.py`. Domain-specific →
  team phải cập nhật theo app của mình.
- **Ràng buộc đề tài** (chi tiết ở `docs/problem-statement.md`):
  - Phê duyệt đề cương thực tập, xử lý ngoại lệ, công nhận quy đổi tín chỉ BẮT BUỘC có
    giảng viên/quản trị viên phê duyệt (HITL) — agent không được tự quyết.
  - Câu trả lời về chính sách phải trích dẫn đúng văn bản quy định hiện hành.
  - Bảo mật thông tin sinh viên và doanh nghiệp.
- **Logging hooks**: `.claude/.cursor/.codex/.gemini/.github` auto-log prompt vào
  `.ai-log/`. KHÔNG disable, KHÔNG bypass `--no-verify`.

## Quy tắc viết tài liệu (docs)

- **Làm xong một chức năng/refactor thì viết tài liệu** vào `docs/changes/`, một file `.md`. Có thể viết
  ngay khi vừa xong hoặc ngay trước khi commit — miễn là có trước khi kết thúc công việc.
- **Tên file**: `YYYYMMDD-<làm-cái-gì>.md` (kebab-case, ngày là ngày làm), ví dụ
  `docs/changes/20261114-refactor-fe.md`.
- **Nội dung**: vấn đề/mục tiêu, đã làm gì (cấu trúc, file chính), cách kiểm tra, và những gì
  chưa kiểm tra hoặc còn lưu ý.
- **Người dùng yêu cầu chỉnh sửa lại tính năng đã có tài liệu → SỬA file docs đó**, không tạo file
  `.md` mới cho cùng tính năng. Cập nhật nội dung cho khớp code; chỉ tạo file mới khi là tính năng khác.

## Commands hay dùng

Slash commands (Claude Code): `/feature`, `/eval` (xem `.claude/commands/`).

## Quyết định kỹ thuật (ADR ngắn)

- **Mock-first LLM**: để template chạy được ngay khi clone → giảm friction sinh viên.
- **External prompt files**: tách prompt khỏi code → mentor review được, diff rõ.
- **Defence-in-depth safety**: guardrail ở cả prompt (safeguards.md) LẪN code
  (safety_node) → chống jailbreak bỏ qua 1 lớp.
- **Retry loop trong graph**: dùng conditional edge thay vì try/except đệ quy.
