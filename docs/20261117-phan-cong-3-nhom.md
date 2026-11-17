# Phân công 3 nhóm chức năng — VIN-15

> Ngày lập: 2026-11-17 · Dựa trên `main` @ `8b6200f` và `docs/PRD.md` §5.
> Mỗi người phụ trách 1 nhóm: **tự test, tự tối ưu** phần của mình. Khi code và tài liệu mâu thuẫn, code trong `src/` là chuẩn.

---

## 1. Toàn bộ function list

| # | Module | Endpoint chính | Hàm lõi (backend) |
|---|---|---|---|
| F1 | **Đăng nhập & phân quyền** (FR-1) | `POST /auth/login`, `/auth/oidc/config`, `/auth/oidc/login`, `/auth/oidc/callback`, `GET /me`, `GET /config` | `core/security.py`: `hash_password`, `verify_password`, `create_token`, `decode_token`, `sign_file_url`, `verify_file_signature` · `core/oidc.py`: `discovery`, `make_state`, `check_state`, `authorize_url`, `fetch_userinfo` · `core/ratelimit.py`: `check_login_allowed`, `record_login_failure`, `record_login_success`, `enforce_usage` · `core/auth.py`: `current_user`, `require_role`, `can_manage_policies` · `api/vin15/deps.py` (kiểm tra phạm vi truy cập) |
| F2 | **Đăng ký thực tập + AI trích xuất (OCR)** (FR-2) | `GET/POST/PATCH /internships`, `/internships/{id}/validate`, `/internships/{id}/submit`, `POST /intake/extract`, `POST /intake/extract/stream` (SSE) | `services/intake.py`: `regex_extract`, `llm_extract`, `normalize_date/phone/tax_code/email/company_name`, `build_suggestions`, `annotate_sources`, `merge_llm`, `extract_suggestions` · `services/documents.py`: `ocr_image`, `ocr_pdf`, `read_document`, `extract_text` · `services/provenance.py`: `locate`, `document_payload` · `services/pii.py` · `workflow/rules.py`: `validate_internship`, `load_cohort_config` |
| F3 | **Duyệt hồ sơ & đề cương (HITL)** (FR-3) | `/internships/{id}/decision`, `/internships/{id}/outline`, `/outlines/{id}/decision`, `GET /approvals/queue`, `/internships/{id}/audit` | `workflow/state_machine.py`: `transition`, `internship_of` · `services/reviewer.py`: `summarize_outline`, `uncovered_outcomes` · `services/lifecycle.py`: `generate_milestones`, `outline_milestone`, `on_outline_submitted`, `on_outline_decided` |
| F4 | **Mốc, minh chứng, nhật ký tuần** (FR-4) | `/internships/{id}/milestones`, `/milestones/{id}/evidence`, `/milestones/{id}/submit`, `/milestones/{id}/review`, `/evidence/{id}/url`, `/files/{id}`, `/internships/{id}/logs`, `PATCH /logs/{id}`, `/logs/{id}/review`, `/logs/{id}/attachments` | `services/storage.py`: `check_file`, `save_file` · `services/lifecycle.py`: `maybe_complete`, `daily_status_job` · `workflow/rules.py`: `milestone_due_date` |
| F5 | **Trợ lý chính sách AI có trích dẫn** (FR-5) | `POST /assistant/chat`, `POST /assistant/chat/stream`, `GET /assistant/conversations/{id}` | `agents/policy_graph.py`: `make_policy_graph` (guard → retrieve → synthesize → verify → finalize), `build_prompt`, `llm_synthesize`, `normalize_markers`, `extractive_answer`, `extractive_synthesize`, `support`, `verify_citations`, `stream_policy_answer`, `answer_policy_question` · `agents/policy_guard.py`: `check_policy_query` · `services/llm.py`: `get_llm`, `llm_available`, `openai_base_url` |
| F6 | **Kho văn bản quy định** (FR-6) | `GET/POST /policies`, `GET /policies/{id}`, `POST /policies/reindex` | `services/policy_index.py`: `normalize`, `tokenize`, `has_accents`, `chunk_document`, `ingest`, `set_embedder`, `get_embedder`, `min_similarity`, `embed_chunks`, `active_chunks`, `search_policy` |
| F7 | **Giám sát rủi ro theo luật** (FR-7) | `GET /risk-flags`, `PATCH /risk-flags/{id}`, `POST /monitor/run` | `services/monitor.py`: `open_key`, `run_for`, `run_all`, `run_for_event`, `scheduler_loop` · `workflow/rules.py`: `evaluate_monitor` · `services/lifecycle.py`: `close_flag` |
| F8 | **Gia hạn mốc (HITL)** (FR-8) | `POST /milestones/{id}/extensions`, `/extensions/{id}/cancel`, `/extensions/{id}/decision`, `GET /internships/{id}/extensions` | `services/lifecycle.py`: `apply_extension` · `services/reviewer.py`: `summarize_extension` · `core/audit.py`: `record`, `record_denied` |
| F9 | **Danh sách tổng hợp & export** (FR-9) | `GET /internships-summary`, `GET /internships-summary/export` (CSV/XLSX) | `api/vin15/summary_routes.py` (lọc, sắp xếp, tìm kiếm, phân trang, export) |
| F10 | **Thông báo, lịch sử, quản trị** (FR-10) | `GET /notifications`, `POST /notifications/read-all`, `/admin/users`, `/admin/assign`, `/admin/cohort`, `PUT /admin/cohort/templates` | `services/notifications.py`: `notify` · `api/vin15/admin_routes.py` |
| F11 | **Agent demo của template** | `POST /api/v1/chat`, `POST /api/v1/chat/resume`, `GET /api/v1/status` | `agents/graph.py` + `agents/nodes/*` + `agents/tools/*` + `agents/guardrails.py` (vòng ReAct có HITL) |

---

## 2. Chia 3 nhóm

| Nhóm | Phạm vi | Function | Khối lượng backend |
|---|---|---|---|
| **Nhóm 1** | Hồ sơ thực tập & AI Intake | F2, F3 | khoảng 1.500 dòng |
| **Nhóm 2** | Tiến độ, Giám sát & Quản trị | F4, F7, F8, F9, F10 | khoảng 1.100 dòng |
| **Nhóm 3** | Trợ lý chính sách AI & Nền tảng bảo mật | F1, F5, F6, F11 | khoảng 1.600 dòng |

### Nhóm 1 — Hồ sơ thực tập & AI Intake (F2 + F3)

**Người phụ trách:** _____________

**Luồng:** sinh viên upload giấy tiếp nhận → OCR/AI trích xuất → điền form → nộp → giảng viên duyệt hồ sơ và đề cương.

**Backend**
- `src/api/vin15/internship_routes.py`
- `src/services/intake.py`, `documents.py`, `provenance.py`, `pii.py`
- `src/services/reviewer.py`: chỉ `summarize_outline`, `uncovered_outcomes`
- `src/services/lifecycle.py`: chỉ `generate_milestones`, `outline_milestone`, `on_outline_submitted`, `on_outline_decided`
- `src/workflow/state_machine.py`
- `src/workflow/rules.py`: chỉ `validate_internship`, `load_cohort_config`
- `prompts/intake_extract.md`, `prompts/reviewer_summary.md`

**Frontend**
- `features/student/`: `RegistrationForm.jsx`, `IntakeProgress.jsx`, `IntakeSource.jsx`, `Outline.jsx`, `StudentHome.jsx`
- `features/lecturer/`: `LecturerQueue.jsx`, `InternshipDetail.jsx`, `DecisionBox.jsx`

**Test**
- `tests/test_vin15/test_intake_pii.py`, `test_intake_provenance.py`, `test_intake_robust.py`, `test_state_machine.py`
- Phần đăng ký và duyệt trong `tests/test_vin15/test_api_flow.py`
- `scripts/ocr_eval.py`, `scripts/make_ocr_samples.py`

**Việc cần test và tối ưu**
- [ ] Chạy OCR trên khoảng 20 bản scan thật. Mục tiêu: các trường định danh (mã số thuế, ngày bắt đầu, ngày kết thúc) đúng ≥ 90%, và không có trường sai nào hiện với độ tin cậy cao mà không kèm cảnh báo.
- [ ] Sửa lỗi nhầm O/0 và l/1 cho cả ngày tháng và số điện thoại (hiện mới sửa cho mã số thuế).
- [ ] Kiểm tra vị trí `boxes` bằng output thật của Tesseract (hiện mới kiểm bằng dữ liệu giả lập).
- [ ] Đặt time budget cho `summarize_outline`, vì hiện nó làm chậm request nộp hồ sơ.
- [ ] Chạy prompt trích xuất với model thật sau lần sửa gần nhất (FR-2.9).
- [ ] Viết test tự động cho các màn hình React đăng ký và duyệt.

### Nhóm 2 — Tiến độ, Giám sát & Quản trị (F4 + F7 + F8 + F9 + F10)

**Người phụ trách:** _____________

**Luồng:** mốc, minh chứng, nhật ký tuần → monitor tạo cảnh báo → gia hạn → bảng tổng hợp, export → admin.

**Backend**
- `src/api/vin15/progress_routes.py`, `monitor_routes.py`, `summary_routes.py`, `admin_routes.py`
- `src/services/monitor.py`, `storage.py`, `notifications.py`
- `src/services/lifecycle.py`: chỉ `maybe_complete`, `daily_status_job`, `apply_extension`, `close_flag`
- `src/services/reviewer.py`: chỉ `summarize_extension`
- `src/workflow/rules.py`: chỉ `evaluate_monitor`, `milestone_due_date`
- `config/cohort.yaml` (template mốc, ngưỡng monitor, giới hạn gia hạn)

**Frontend**
- `features/student/`: `Timeline.jsx`, `StudentLogs.jsx`, `ExtensionList.jsx`
- `features/lecturer/`: `Flags.jsx`, `StudentList.jsx`
- `features/admin/AdminHome.jsx`
- `features/shared/EvidenceLink.jsx`
- `components/layout/Notifications.jsx`

**Test**
- `tests/test_vin15/test_monitor_rules.py`
- Phần summary và export trong `tests/test_vin15/test_summary_ratelimit.py`
- Phần milestone, log, evidence, extension trong `tests/test_vin15/test_api_flow.py`

**Việc cần test và tối ưu**
- [ ] Xử lý múi giờ (OQ-9): server đang chạy UTC nên "07:00" thực chất là 14:00 giờ Việt Nam, và "hôm nay" đang tính theo ngày UTC.
- [ ] Rút ngắn độ trễ chuyển `overdue`: hiện mốc có thể trễ tới khoảng 24 giờ mới chuyển trạng thái.
- [ ] Tối ưu query (N+1) của `/internships-summary` khi có nhiều hồ sơ, rồi load test cho list và export.
- [ ] Kiểm tra lại trên Postgres: khóa ngoại, trigger append-only của `audit_event`, upsert template mốc.
- [ ] Kiểm tra upload minh chứng: sai magic bytes, file quá 10 MB, link ký đã hết hạn.
- [ ] Viết test tự động cho các màn hình React timeline, flags, admin.

### Nhóm 3 — Trợ lý chính sách AI & Nền tảng bảo mật (F1 + F5 + F6 + F11)

**Người phụ trách:** _____________

**Luồng:** đăng nhập/SSO, phân quyền, rate limit → kho quy định (chunk, embedding) → trợ lý RAG có kiểm chứng trích dẫn.

**Backend**
- `src/agents/policy_graph.py`, `policy_guard.py`
- `src/services/policy_index.py`, `llm.py`
- `src/api/vin15/assistant_routes.py`, `auth_routes.py`, `deps.py`
- `src/core/`: `security.py`, `oidc.py`, `ratelimit.py`, `auth.py`, `audit.py`
- `prompts/policy_assistant.md`, `citation_rules.md`, `safeguards.md`, `system_prompt.md`
- `eval/` (bộ đánh giá)
- Agent demo: `src/agents/graph.py`, `nodes/`, `tools/`, `guardrails.py`, `src/api/routes.py`

**Frontend**
- `features/shared/`: `Assistant.jsx`, `Policies.jsx`
- `features/auth/Login.jsx`
- `context/AuthContext.jsx`, `context/ChatContext.jsx`

**Test**
- `tests/test_vin15/test_policy_assistant.py`, `test_stream_sso_embedding.py`
- Phần rate limit trong `tests/test_vin15/test_summary_ratelimit.py`
- `tests/test_agents/*`, `tests/test_api/test_routes.py`, `tests/test_services/test_llm_cascade.py`
- `python eval/run_eval.py`, `scripts/llm_e2e.py`, `scripts/sso_e2e.py`

**Việc cần test và tối ưu**
- [ ] Xây bộ eval chất lượng câu trả lời lớn hơn (R16, OQ-4). Hiện chỉ có 10 câu cho model thật và 8 câu để hiệu chỉnh ngưỡng embedding.
- [ ] Viết bộ câu hỏi tấn công thử (adversarial) cho `policy_guard`, vì guard hiện chỉ dùng regex (MET-8).
- [ ] Cải thiện bước kiểm tra grounding: hiện yêu cầu ≥ 60% từ trùng với điều khoản nên câu diễn đạt lại đúng vẫn bị loại.
- [ ] Giảm p95 khi dùng model thật (với budget 8 giây, model trên CPU hầu như chỉ trả về trích dẫn nguyên văn).
- [ ] Chuyển rate limit ra store dùng chung (ví dụ Redis) để chạy được nhiều worker (NFR-12).
- [ ] Bảo mật: verify chữ ký `id_token` của SSO, thu hồi được JWT, bắt buộc đổi `JWT_SECRET` khi chạy production.

---

## 3. File dùng chung và quy ước làm việc

**File dùng chung, không có chủ riêng.** Sửa các file này phải mở PR và có ít nhất 1 người nhóm khác review:
- `src/models/orm.py`, `src/models/schemas.py`, `src/db.py`, `src/config.py`, `src/seed.py`, `src/main.py`
- `src/api/vin15/serializers.py`
- `frontend/src/lib/api.js`, `frontend/src/components/ui/*`, `frontend/src/App.jsx`

**File chia theo hàm.** `lifecycle.py`, `reviewer.py`, `rules.py` có hàm thuộc nhiều nhóm (xem mục 2). Ai sửa hàm nào thì chỉ sửa hàm của nhóm mình.

**Quy trình**
1. Tạo branch `feature/<nhom>-<viec>` từ `main`, ví dụ `feature/g1-ocr-digit-fix`.
2. Trước khi mở PR, chạy toàn bộ test, không chỉ phần của mình:
   `pytest tests/ -v`, `ruff check .` và `python eval/run_eval.py` (bắt buộc với nhóm 3).
3. Làm xong một việc thì ghi tài liệu vào `docs/changes/YYYYMMDD-<viec>.md` (theo `CLAUDE.md`).
4. Không tắt logging hook, không dùng `--no-verify`.

**Ràng buộc chung (không được phá)**
- Duyệt đề cương, xử lý ngoại lệ, gia hạn, quy đổi tín chỉ: **bắt buộc người duyệt (HITL)**, không AI hay tiến trình tự động nào được tự quyết.
- Câu trả lời về chính sách phải **trích dẫn đúng văn bản đang có hiệu lực**.
- Không lộ PII của sinh viên và doanh nghiệp, không gửi mã số thuế, email, số điện thoại sang model.
