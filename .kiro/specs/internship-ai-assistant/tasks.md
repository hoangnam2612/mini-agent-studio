# Tasks — VIN-15: Hệ thống hỗ trợ thực tập bằng AI

> Kiro spec · Giai đoạn 3/3 · **Phiên bản 2: thu hẹp phạm vi**.
> Task đánh dấu `*` là tùy chọn (thuộc vai trò QTV hoặc phần trang trí thêm).

## Phase 0 — Nền móng

- [ ] 1. Hạ tầng
  - [ ] 1.1 Docker Compose gồm `web` (Next.js), `api` (FastAPI), `db` (Postgres + pgvector); cập nhật `.env.example`.
  - [ ] 1.2 Alembic migrations; cập nhật `PROJECT_CONTEXT.md`/`CLAUDE.md` cho domain VIN-15.
  - [ ] 1.3 `config/cohort.yaml` (đợt, mẫu mốc, luật) + `scripts/seed.py` (30 SV, 3 GV, 1 đợt, phân công).
  - _Requirements: NFR-2, R4.1, A1_
- [ ] 2. Xác thực & phân quyền
  - [ ] 2.1 Đăng nhập JWT với tài khoản demo; `current_actor()` + `require_role`.
  - [ ] 2.2 Scoping ở repository (SV chỉ thấy mình, GV chỉ thấy SV được phân công); test P5.
  - [ ] 2.3* Adapter OIDC (Keycloak).
  - _Requirements: R1.1–1.5_
- [ ] 3. Workflow core
  - [ ] 3.1 Bảng `audit_event` append-only (trigger chặn UPDATE/DELETE).
  - [ ] 3.2 `transition()` + `STATE_GRAPH` / `DECISION_EDGES` cho hồ sơ, đề cương, mốc, gia hạn; test P1, P7.
  - _Requirements: R3.3–3.5, R12.5, R15.3_

## Phase 1 — Hồ sơ, mốc, nhật ký

- [ ] 4. Model + migration: cohort, company, internship, outline, milestone_template, milestone, evidence, log_entry, notification.
  - _Requirements: R2, R4, R5_
- [ ] 5. Đăng ký thực tập
  - [ ] 5.1 API CRUD + submit; rule engine `validation` kèm citation.
  - [ ] 5.2 UI form đăng ký cho SV.
  - _Requirements: R2.1, R2.3–2.5, R2.7_
- [ ] 6. Phê duyệt hồ sơ và đề cương
  - [ ] 6.1 API nộp đề cương; `/approvals/queue`; endpoint decision có lý do bắt buộc.
  - [ ] 6.2 UI hàng chờ của GV và màn hình duyệt.
  - _Requirements: R3.1, R3.3–3.5_
- [ ] 7. Mốc
  - [ ] 7.1 Sinh mốc khi hồ sơ được duyệt; job hằng ngày chuyển `pending → overdue`.
  - [ ] 7.2 Upload minh chứng (kiểm MIME/size, sha256, URL tải có ký).
  - [ ] 7.3 UI timeline mốc cho SV; GV chấp nhận/trả lại minh chứng.
  - _Requirements: R4.2–4.4, R5.2–5.3, R15.1_
- [ ] 8. Nhật ký tuần: API + UI cho SV; GV nhận xét.
  - _Requirements: R5.1, R5.3_

## Phase 2 — Trợ lý AI chính sách

- [ ] 9. Kho văn bản quy định
  - [ ] 9.1 `policy_doc`/`policy_chunk`; API upload + metadata hiệu lực + supersede.
  - [ ] 9.2 Chunker theo Chương/Điều/Khoản + embedding + `tsvector`; test P3.
  - [ ] 9.3 Soạn 3–4 văn bản quy chế mẫu (có 1 văn bản bị thay thế để demo).
  - [ ] 9.4 UI quản lý văn bản (cho QTV, hoặc GV điều phối).
  - _Requirements: R9.1–9.3_
- [ ] 10. Policy Assistant (mở rộng `src/agents/`)
  - [ ] 10.1 Tool `search_policy` (hybrid, filter do server inject) thay `search_knowledge`.
  - [ ] 10.2 Tool `get_my_context` + PII Redactor; test P6.
  - [ ] 10.3 Node `verify_citations` + render nguồn; test P2.
  - [ ] 10.4 Cập nhật `prompts/system_prompt.md`, `citation_rules.md`, `safeguards.md` (cấm cam kết quyết định, từ chối khi không có nguồn).
  - [ ] 10.5 Mở rộng guardrail: hỏi về SV khác, ép phê duyệt, injection.
  - [ ] 10.6 Bộ smoke test khoảng 10 câu với mock LLM (có nguồn / không nguồn / ép quyết định / injection).
  - _Requirements: R8.1–8.7, R15.2_
- [ ] 11. API chat SSE + lưu hội thoại và trích dẫn; UI chat có panel nguồn; nút "Tạo yêu cầu gia hạn" mở form điền sẵn.
  - _Requirements: R8.6, R8.8, NFR-1_

## Phase 3 — AI chuẩn hóa hồ sơ & gợi ý cho GV

- [ ] 12. Intake Extractor
  - [ ] 12.1 Parse PDF/DOCX → LLM structured output `InternshipDraft` có độ tin cậy từng trường.
  - [ ] 12.2 Chuẩn hóa ngày/email/SĐT/mã số thuế; khớp `company` theo mã số thuế.
  - [ ] 12.3 `/intake/extract` + UI "điền từ file", đánh dấu trường AI điền, bước xác nhận.
  - _Requirements: R2.2–2.3, R2.6_
- [ ] 13. Reviewer Summarizer: tóm tắt đề cương + liệt kê CĐR chưa nhắc tới (R3.2); tóm tắt yêu cầu gia hạn + điều khoản (R12.2). Hiển thị nhãn "Gợi ý của AI", ẩn đi khi AI lỗi.
  - _Requirements: R3.2, R12.2_

## Phase 4 — Giám sát & gia hạn

- [ ] 14. Monitor theo luật
  - [ ] 14.1 Các hàm `check` (a)–(d) + registry; đọc luật từ `cohort.yaml`.
  - [ ] 14.2 APScheduler hằng ngày + hook theo sự kiện từ workflow.
  - [ ] 14.3 Upsert `risk_flag` không trùng (unique partial index); test P4.
  - [ ] 14.4 Notification in-app; UI chuông thông báo.
  - [ ] 14.5 UI "SV có cờ rủi ro" cho GV: acknowledge / resolve / dismiss kèm lý do.
  - _Requirements: R10.1–10.7_
- [ ] 15. Yêu cầu gia hạn mốc
  - [ ] 15.1 Bảng `extension_request`; API tạo/hủy (SV) và quyết định (GV).
  - [ ] 15.2 Khi duyệt: dời `due_at`, gỡ `overdue`, đóng cờ overdue liên quan, ghi audit trong 1 transaction; test P8.
  - [ ] 15.3 UI cho SV (tạo, theo dõi) và GV (duyệt); trang lịch sử audit của hồ sơ.
  - _Requirements: R12.1–12.5_

## Phase 5 — Hoàn thiện

- [ ] 16. Integration test toàn luồng (testcontainers) + E2E Playwright cho 2 vai trò chính.
  - _Requirements: NFR-5_
- [ ] 17.* Màn hình QTV: cấu hình đợt/mốc, quản lý tài khoản và phân công (thay cho YAML/seed).
  - _Requirements: R4.1, R1.4_
- [ ] 18. README, ARCHITECTURE.md, ADR trong WORKLOG.md; kịch bản demo 5 phút: SV đăng ký từ file → GV duyệt → SV hỏi AI có trích dẫn → Monitor cảnh báo quá hạn → SV xin gia hạn → GV duyệt.

---

### Ma trận truy vết

| Requirement | Tasks |
|---|---|
| R1 Xác thực & phân quyền | 2, 17* |
| R2 Hồ sơ & chuẩn hóa | 5, 12 |
| R3 Duyệt hồ sơ / đề cương | 3, 6, 13 |
| R4 Mốc | 1.3, 7, 17* |
| R5 Nhật ký & minh chứng | 7, 8 |
| R8 Trợ lý AI | 10, 11 |
| R9 Kho quy định | 9 |
| R10 Monitor | 14 |
| R12 Gia hạn mốc | 3, 13, 15 |
| R15 Bảo mật | 2, 3.1, 7.2, 10.2 |
| R7 Danh sách tổng hợp | Đã build ngày 2026-11-14 (ngoài kế hoạch ban đầu): `src/api/vin15/summary_routes.py`, màn hình Sinh viên / Danh sách |
| R6, R11, R13, R14, R16 | Backlog — xem `requirements.md` §6 |

---

## Trạng thái triển khai (cập nhật 2026-11-14, đọc từ code)

Chi tiết từng yêu cầu: `docs/PRD.md` §5. Tóm tắt theo task:

| Task | Trạng thái | Ghi chú / lệch so với design |
|---|---|---|
| 1 Hạ tầng | Xong | Compose 3 service: `db` (Postgres 16), `backend` (API + giao diện tĩnh), `proxy` (Caddy HTTPS). Chưa có Alembic: `create_all` + bổ sung cột thiếu trong `init_db`. |
| 2 Xác thực & phân quyền | Xong | JWT tài khoản demo + SSO/OIDC (authorization code, khớp tài khoản nội bộ theo email) khi có `OIDC_ISSUER`. Mới thử với IdP giả lập (MockTransport), chưa với Keycloak thật. |
| 3 Workflow core | Xong | `transition()` + trigger append-only cho SQLite và Postgres. |
| 4–8 Hồ sơ, phê duyệt, mốc, nhật ký | Xong | Có UI đính kèm file cho nhật ký. |
| 9 Kho quy định | Xong | BM25 có dấu + embedding (JSON, cosine trong RAM) khi có API key; chưa dùng pgvector. |
| 10 Policy Assistant | Xong | Pipeline tuyến tính thay vì ReAct (lý do ở docstring `policy_graph.py`). |
| 11 Chat API | Xong | `POST /assistant/chat/stream` (SSE): sự kiện tiến độ từng bước, rồi câu trả lời đã kiểm chứng theo từng đoạn. |
| 12 Intake Extractor | Xong | Đường LLM chưa chạy với API key thật; mặc định regex. Không OCR file scan. |
| 13 Reviewer Summarizer | Xong | CĐR chưa nhắc tới tính theo từ khóa. |
| 14 Monitor | Xong | Vòng lặp asyncio trong process thay cho APScheduler. Thêm: chặn tạo lại cờ đã bác bỏ trong 7 ngày. |
| 15 Gia hạn | Xong | UI cho đính kèm minh chứng; giới hạn 14 ngày nằm trong `cohort.yaml`. |
| 16 Kiểm thử | Xong | 69 test pytest (SQLite có bật khóa ngoại) + kiểm tra tay trên Postgres; smoke UI jsdom (26 bước) và kiểm tra mobile 390 px bằng Chrome headless (10 màn hình) thay Playwright; chưa có testcontainers. |
| 17* Màn hình QTV | Xong | Tạo tài khoản, phân công GV, sửa mẫu mốc. |
| 18 Tài liệu | Xong | README, PROJECT_CONTEXT, ARCHITECTURE.md, ADR trong WORKLOG.md, PRD. |

### Bổ sung ngày 2026-11-14 (vòng 3)

| Hạng mục | Kết quả |
|---|---|
| R7 danh sách tổng hợp | Lọc (đợt, ngành, GV, trạng thái, mức rủi ro), tìm kiếm, sắp xếp, phân trang, xuất CSV/XLSX theo phạm vi quyền, audit `exported`. |
| Bảo vệ endpoint demo template | `/api/v1/chat`, `/chat/resume` bắt buộc đăng nhập; thread gắn với người dùng. |
| Giới hạn tần suất | Khóa tài khoản sau 5 lần sai/15 phút, 30 lần thử/IP/phút, trợ lý 20 câu/phút, intake 10 lần/phút (in-memory). |
| Đường LLM thật | Chạy với Ollama (Qwen2.5 1.5B/0.5B, bge-m3) qua API tương thích OpenAI — `scripts/llm_e2e.py`. Phát hiện và sửa: model bỏ trích dẫn, trích dẫn lạc đề, số liệu sai; thêm kiểm tra bám nguồn, ngân sách thời gian 8 s. |
| SSO thật | Keycloak 25 — `scripts/sso_e2e.py`, 8/8. |
