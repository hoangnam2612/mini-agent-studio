# VIN-15 AI Internship Support System — Product Requirements Document (PRD)

> **Status:** Draft for review
> **Version:** 0.6
> **Date:** 2026-11-14
> **Scope:** the internship portal served at `/` (React app in `frontend/`, built to `frontend/dist`) and the REST API at `/api/v1`, for two main roles (Student, Lecturer) and one optional role (Administrator)
> **Basis:** read from the code on `main` at `c3e71ab` (PR #1 backend and PRD, PR #3 React frontend), plus three local fixes not yet committed (CSP for the React fonts and theme script, a duplicated AI label; see §13), and from the Kiro spec in `.kiro/specs/internship-ai-assistant/` (version 2, reduced scope, with R7 brought back)
> **Problem statement:** VIN-15, Higher Education & Academic Administration track
> **Companion documents:** `BRIEF.md` (project brief) · `docs/wireframe/` (wireframes: 14 screens, desktop and mobile, PDF and PNG)
> **Earlier versions:** v0.1 (Vietnamese, 2026-11-13) to v0.5 are replaced by this document. The change log in section 15 lists what changed.

## 1. Document control

### 1.1 Purpose

This PRD defines what the internship portal must do, what it does today, and where it
falls short. Each requirement has an ID, an acceptance criterion and a status taken
from the code, so the document can be checked against the product. The ID in brackets,
such as `(R3.5)`, points to the requirement in the Kiro `requirements.md`.

### 1.2 Conventions

- **Priority:** P0 release-blocking, P1 important, P2 later.
- **Status:** **Built** (matches the criterion), **Partial** (works, narrower than the criterion), **Not built**.
- Names in `code font` are real routes, classes or files. Vietnamese UI labels are given in **bold**.
- **No-LLM mode** means no `OPENAI_API_KEY` is set; every AI feature then runs on deterministic rules. The pytest suite runs in this mode, with models, embedders and the IdP replaced by scripted functions at the same seams.
- **Live model** means the real `ChatOpenAI` / `OpenAIEmbeddings` code path pointed at an OpenAI-compatible endpoint. It was run on 2026-11-14 against Ollama 0.5.7 serving Qwen2.5 1.5B and 0.5B (chat) and bge-m3 (embeddings) on the development laptop's CPU (`scripts/llm_e2e.py`).
- **api.openai.com** was called on 2026-11-14 in two runs.
  - **First run:** the key in `.env` had expired, so every endpoint answered `401`. That run found two bugs and one privacy gap, all fixed (§13). It also confirmed the degraded path: with the provider failing, the assistant answers from verified quotes (`mode=extractive_error`).
  - **Second run:** with a new key (gpt-4o for answers, gpt-4o-mini for extraction and summaries, text-embedding-3-small), `scripts/llm_e2e.py` passed every check (§11.1).

### 1.3 Out of scope for this document

The following are not specified here:

- **Deferred in the spec's Backlog:** company mentors grading through a link (R6), the AI quality evaluation set (R16), credit recognition (R11), exception types other than a milestone extension and multi-step approval chains, AI scoring of learning-outcome drift, LMS sync (R13), and the BI dashboard (R14).
- **Template code:** `eval/`, `docs/guide/` and the AI-usage logging hooks. The template's demo agent endpoints (`/api/v1/chat`, `/api/v1/chat/resume`) still run inside the app but now require sign-in (FR-1.9).

## 2. Product definition

### 2.1 Summary

**Students:**
- Register their internship. They can upload the company's acceptance letter, and the system fills and normalizes the form.
- Submit an outline, evidence for each mandatory milestone, and a weekly log.
- Ask an assistant about the rules and get answers that cite the regulation in force.

**The assigned lecturer** is the only one who decides:
- Approves the registration, the outline and any milestone extension.
- Reviews logs and evidence.
- Works from a filterable list of their students that can be exported to a spreadsheet.

**A monitor** runs on rules every day and after each event. It flags milestones that are due soon, overdue, missing evidence or short on hours, and notifies the right person. It cannot change the state of a record.

### 2.2 Users

| Role | Kind | Sign-in | Data scope |
|---|---|---|---|
| Student (`student`) | Main | Local account (JWT) or SSO | Own record only |
| Lecturer (`lecturer`) | Main | Local account (JWT) or SSO | Assigned students. A lecturer with `is_coordinator` manages regulations when the Administrator role is off. |
| Administrator (`admin`) | Optional (`ENABLE_ADMIN_ROLE`) | Local account (JWT) or SSO | Accounts, assignments, milestone templates, regulations, the cohort-wide list |

Two system actors are not users:
- **Policy assistant:** `src/agents/policy_graph.py`.
- **Monitor:** `src/services/monitor.py`.

The monitor acts as `Actor(kind="system")`. The assistant has no write tool.

### 2.3 Objective

Cut the repeated questions and manual tracking that lecturers handle, while every academic decision stays with a person.

### 2.4 Hypothesis

There are three conditions:
- Policy answers always carry a source that can be checked.
- A registration is checked against the regulation when it is submitted.
- Risks are flagged before the deadline.

If all three hold, lecturers get fewer repeated questions, fewer registrations come back for format errors, and late students are found sooner, without handing any decision to the AI.

## 3. Goals and non-goals

### 3.1 Goals

- Normalize and check registrations against the regulation before a lecturer sees them. Every error names the clause it comes from.
- Answer policy questions only from regulations in force. Every sentence carries a citation, and every sentence and number must be found in the cited clause. Say "not found" when there is no source.
- Let only the assigned lecturer approve a registration, outline or extension, with a reason and a trail that cannot be edited.
- Flag due-soon, overdue, missing-evidence and low-hours risks early, and notify the right person.
- Give lecturers and the Administrator one list of all records, with filters, sorting, search and export.
- Keep student data inside its scope: between students, between lecturers, and away from the AI provider.

### 3.2 Non-goals

- Matching students with companies, contracts, e-signatures.
- Grading, credit recognition or credit transfer.
- LMS/SIS sync, BI dashboards and charts.
- Accounts for company mentors.
- Exceptions other than a milestone extension (changing company, deferral, etc.).

## 4. User journey

The interface is a React 18 single-page app built with Vite (`frontend/`), with hash routing (`react-router` HashRouter) so the SSO callback `#/sso/<token>` keeps working. FastAPI serves the build (`frontend/dist`) behind Caddy at `https://localhost`; the older plain-JS app in `web/` is only a fallback when no build exists. Layout: a sidebar per role (a top header on phones), the Lexend typeface, an Auto / Light / Dark switch, and on the student home a "next step" line above a numbered milestone path. Screen-by-screen wireframes are in `docs/wireframe/`. The login page shows **Đăng nhập bằng tài khoản trường (SSO)** when OIDC is configured. Five wrong passwords in 15 minutes lock the account for 15 minutes.

**Student** (`#/`, `#/logs`, `#/assistant`, `#/policies`):

1. **Create.** A student with no record sees the cohort window and **Tạo hồ sơ đăng ký**.
2. **Fill from file.** The student uploads an acceptance letter (PDF/DOCX/TXT). A table shows each suggested field with its confidence. **Điền vào form** fills the form, colors those fields purple and labels them "AI điền — hãy kiểm tra". Editing a field removes its AI label.
3. **Check and submit.** **Kiểm tra theo quy chế** lists errors with their source clause. **Xác nhận & nộp hồ sơ** succeeds only when every rule passes.
4. **Track.** Once approved, the student sees:
   - A milestone timeline: due date, days left or overdue, required evidence, source clause.
   - Evidence upload, **Nộp mốc**, and **Xin gia hạn** (with optional supporting evidence).
   - The outline box and open warnings.
5. **Logs:** one entry per week with hours, content, difficulties and attachments. A returned log can be edited and resent.
6. **Assistant:** the answer streams in.
   - Progress steps show first (**Kiểm tra câu hỏi**, **Tra cứu văn bản đang hiệu lực**, …), then the verified answer, then **Nguồn** with expandable excerpts.
   - An answer quoted verbatim from the regulation is labelled **Trích nguyên văn quy định**. This happens when no model is configured, or when the model ran out of time or could not write a sourced answer.
   - A decision request gets a note and a link to the milestones.

**Lecturer** (`#/` approval queue, `#/students`, `#/internship/:id`, `#/flags`):

1. **Queue:** pending registrations (AI-filled fields are labelled), outlines with a "Gợi ý của AI" box (summary and learning outcomes not mentioned), and extension requests with a summary, related clauses and any attached evidence. Each item has a reason box and decision buttons.
2. **Students:** a table of assigned records.
   - Columns: student, company, state, % of milestones done, next milestone and its due date, open warnings and the highest severity.
   - Filters for state, program and risk, plus search, sortable columns and paging.
   - **Xuất CSV** and **Xuất Excel** export exactly the filtered rows.
3. **Student detail:** accept or return evidence and logs; read the audit history.
4. **Warnings:** acknowledge, resolve, or dismiss (a note is required).

**Administrator** (optional): edit milestone templates, assign lecturers, create accounts, upload and reindex regulations, **Chạy giám sát ngay**, and **Danh sách**. The list is the same table across all lecturers, with a lecturer filter, read-only.

A bell in the top bar shows the number of unread notifications. Opening it marks them all as read. On phones (390 px wide) the sidebar becomes a header above the content, and no page scrolls horizontally.

## 5. Functional requirements

### 5.1 Authentication and access — `POST /auth/login`, `/auth/oidc/*`, `GET /me`, `src/api/vin15/deps.py`, `src/core/ratelimit.py`

| ID | Requirement | Priority | Acceptance criterion | Status |
|---|---|---|---|---|
| FR-1.1 | Sign in and get exactly one role: `student`, `lecturer` or `admin` (R1.1). | P0 | A wrong password returns 401 and writes a `login_failed` audit event. | Built (HS256 JWT written with the stdlib, PBKDF2 passwords) |
| FR-1.2 | When OIDC is configured, sign in through SSO (R1.2). | P0 | Authorization code flow with a client secret and an HMAC-signed `state` that expires in 10 minutes. The IdP account is matched to a local account by verified email, then by `preferred_username`; the role comes from the local account. An unknown account, a bad `state`, a rejected code or an IdP error each redirect to `#/sso-error/…` and are audited. | Built. Run against Keycloak 25.0.6 (`scripts/sso_e2e.py`, 8/8): the full browser flow through Keycloak's login form maps `chi.le` → `sv03` and `tam.le` → `gv01`; a wrong password yields no code; an account unknown to the portal and a tampered `state` are refused. Also unit-tested against a mocked IdP. |
| FR-1.3 | A student sees only their own record (R1.3). | P0 | Every route that reads by id returns 403 for another student's id; lists never contain other records. | Built |
| FR-1.4 | A lecturer sees only assigned students (R1.4). | P0 | Same as FR-1.3. After reassignment the previous lecturer gets 403. | Built |
| FR-1.5 | Out-of-scope access returns 403 and is audited (R1.5). | P0 | An `access_denied` event is written even though the request fails (separate session). | Built |
| FR-1.6 | The Administrator role can be turned off. | P1 | With `ENABLE_ADMIN_ROLE=false`, `admin` cannot sign in (403) and `/admin/*` returns 404. | Built |
| FR-1.7 | Lock an account after repeated failed sign-ins. | P0 | 5 failures in 15 minutes return 429 with `Retry-After`, even for the right password. Other accounts are unaffected. A successful sign-in clears the count. Throttled attempts are audited (`login_throttled`). | Built (in-memory, per process) |
| FR-1.8 | Limit sign-in attempts per IP. | P1 | More than 30 attempts per minute from one IP return 429. Behind Caddy, the client IP is read from `X-Forwarded-For` (`--proxy-headers`). | Built (in-memory, per process) |
| FR-1.9 | The template's demo agent endpoints require sign-in. | P0 | `/api/v1/chat` and `/api/v1/chat/resume` return 401 without a token. The LangGraph thread is keyed by user, so a known `session_id` cannot be resumed by someone else. | Built |

### 5.2 Registration and AI normalization — `/internships`, `POST /intake/extract`

| ID | Requirement | Priority | Acceptance criterion | Status |
|---|---|---|---|---|
| FR-2.1 | The form holds the company (name, tax code, address), the mentor (name, email, phone), position, description, start and end dates, and mode (R2.1). | P0 | One non-rejected record per student per cohort; a second one returns 409. | Built |
| FR-2.2 | Extract the fields from a PDF/DOCX acceptance letter as **suggestions** with a confidence (R2.2). | P0 | Fields below 0.5 confidence, or that cannot be normalized, are left empty with `needs_manual`. At most 10 extractions per user per minute. | Built. Live model: Qwen2.5 1.5B extracted all 11 fields of the sample letter correctly (`source=llm`). No-LLM mode uses label-based regex. Scanned PDFs and images are not read (no OCR); the spec asks only for PDF/DOCX. |
| FR-2.3 | Normalize dates, email, phone and tax code; match a known company by tax code (R2.3). | P0 | On a tax-code match, the catalog's name and address are used. | Built |
| FR-2.4 | Check on submit: required fields, end after start, at least 8 weeks, inside the cohort window (R2.4). | P0 | Rules are declared in `config/cohort.yaml`; each `check` is a named function in `VALIDATION_CHECKS`, with no `eval`. | Built |
| FR-2.5 | Each failed check names its clause (R2.5). | P0 | 422 returns `errors[]` with `rule_id`, `message` and `citation{doc,path}`. | Built |
| FR-2.6 | The student confirms before submitting; AI-filled fields are marked (R2.6). | P0 | Suggestions are never written to the record by themselves; `ai_fields` is stored and shown to the lecturer. | Built |
| FR-2.7 | Submitting moves `draft → submitted` and notifies the lecturer (R2.7). | P0 | An in-app notification goes to the assigned lecturer. | Built |
| FR-2.8 | A student edits a record in `draft` or `revision_requested`; `version` prevents lost updates. | P1 | An edit with a stale version returns 409. | Built |

### 5.3 Registration and outline approval (HITL) — `/internships/{id}/decision`, `/internships/{id}/outline`, `/outlines/{id}/decision`, `GET /approvals/queue`

| ID | Requirement | Priority | Acceptance criterion | Status |
|---|---|---|---|---|
| FR-3.1 | Submitted registrations and outlines go to the assigned lecturer's queue (R3.1). | P0 | | Built |
| FR-3.2 | Outline suggestions: a summary and the learning outcomes not mentioned, labelled "Gợi ý của AI" (R3.2). | P1 | If the AI fails, `ai_summary` is `null` and the lecturer can still decide. | Built. Live model wrote the summary (`source=llm`). Outcomes not mentioned are found by keywords in `cohort.yaml`. |
| FR-3.3 | Only the assigned lecturer can move a record to `approved`, `rejected` or `revision_requested` (R3.3). | P0 | A student, another lecturer or the admin gets 403; the admin's detail screen shows no review buttons. | Built |
| FR-3.4 | No AI agent or automated process can take a decision edge (R3.4). | P0 | `transition()` raises `ForbiddenTransition` for any `actor.kind ≠ human`, even with the lecturer's own id. | Built (property test P1) |
| FR-3.5 | `rejected` and `revision_requested` need a reason; every decision is audited with who, when, reason and version (R3.5). | P0 | A missing reason returns 422. `audit_event.after` holds `status` and `version`. A stale version returns 409. | Built |
| FR-3.6 | Approval creates the milestones from the cohort templates; if the start date has passed, the record moves to `in_progress` (R4.2). | P0 | | Built |
| FR-3.7 | The milestone **Đề cương được duyệt** follows the outline: submitted → `submitted`, approved → `accepted`, rejected or sent back → `rejected`. | P1 | Students cannot submit it and lecturers cannot review it directly (409). | Built |

### 5.4 Milestones, evidence, logs — `/milestones/*`, `/internships/{id}/logs`, `/logs/*`, `/evidence/{id}/url`, `/files/{id}`

| ID | Requirement | Priority | Acceptance criterion | Status |
|---|---|---|---|---|
| FR-4.1 | Cohort milestone templates hold name, due rule (`anchor` start/mid/end plus `offset_days`), required evidence and source clause, entered by the Administrator on screen or read from YAML (R4.1). | P0 | Saving templates upserts by code and applies only to records approved afterwards. Milestones already created keep their copy, and their link is cleared if their template is removed. | Built |
| FR-4.2 | Milestone states `pending → submitted → accepted | rejected`; past due becomes `overdue` (R4.3). | P0 | The daily job moves late milestones to `overdue`. | Built |
| FR-4.3 | A timeline for the student with due date, state and days left (R4.4). | P0 | | Built |
| FR-4.4 | Evidence is stored privately; PDF/DOCX/PNG/JPG are checked by **extension and magic bytes**, up to 10 MB (R5.2). | P0 | A mislabelled or oversized file returns 422. Files are stored under their sha256. | Built |
| FR-4.5 | Files download only through a signed URL that expires after 300 seconds (R15.1). | P0 | A bad or expired signature returns 403; out-of-scope users cannot get a URL. | Built |
| FR-4.6 | The lecturer accepts or returns a milestone; returning needs a comment (R5.3). | P0 | When every milestone is `accepted` and the record is `in_progress`, the record becomes `completed`. | Built |
| FR-4.7 | Weekly log: content, difficulties, hours (0–80), attachments (R5.1). | P0 | A second entry for the same week returns 409. | Built |
| FR-4.8 | The lecturer accepts or returns a log; the student edits a returned log and resends it (R5.3). | P1 | | Built |

### 5.5 Policy assistant with citations — `POST /assistant/chat`, `POST /assistant/chat/stream`, `src/agents/policy_graph.py`

LangGraph pipeline: `guard → retrieve → synthesize → verify → finalize`.

| ID | Requirement | Priority | Acceptance criterion | Status |
|---|---|---|---|---|
| FR-5.1 | Retrieve only `active` documents in force on the day of the question; the server applies the filter (R8.1). | P0 | A superseded or not-yet-effective document is never returned. | Built (property test P3) |
| FR-5.2 | Send only minimal context: role, program, cohort, record state, mode, next milestone; never name, student code, email or phone (R8.2). | P0 | | Built |
| FR-5.3 | Every claim carries a citation: document code, Chapter/Article/Clause, effective date (R8.3). | P0 | The answer shows `[n]` and a source list with excerpts. | Built |
| FR-5.4 | Verify each sentence before it is shown (R8.4). | P0 | <ul><li>The model cites `[n]` for the clauses it was given; the server maps `[n]` to chunk ids, and a number outside the list drops the sentence.</li><li>A kept sentence has ≥ 4 words and ≥ 60% of its content words in the cited clause.</li><li>**Every number in the sentence appears in the clause body** (article headings and clause numbers excluded).</li><li>A correct sentence without a citation is attached to the clause it matches.</li><li>On failure the model is asked once more; if that also fails, a verbatim quote of the retrieved clauses is returned (`mode=extractive_fallback`).</li></ul> | Built (property test P2; tests with models that invent ids, cite off-topic, state wrong numbers, write empty sentences). Rules added after the live-model run exposed off-topic citations and a wrong number that the earlier id-only check let through. |
| FR-5.5 | When no passage clears the threshold, answer "not found" and suggest contacting the lecturer (R8.5). | P0 | A passage needs BM25 ≥ 2.0 **and** ≥ 40% of the question's keywords, or embedding cosine ≥ the threshold calibrated for the embedding model (0.38 for text-embedding-3-small, 0.50 for bge-m3; `EMBEDDING_MIN_SIMILARITY` overrides it). If the model answers `KHONG_TIM_THAY`, the answer is "not found". | Built. Live run: "Giá vàng hôm nay bao nhiêu?" and "Thủ đô của Pháp là gì?" → not found in 0.1 s. |
| FR-5.6 | A request for a decision ("em có được gia hạn không") gets the rule explained, no promise, and a pointer to the extension request (R8.6). | P0 | Returns `suggest_extension=true`. The assistant has no write tool. | Built |
| FR-5.7 | Refuse and log questions about other students and prompt injection (R8.7). | P0 | A student code other than the asker's, phrases such as "hồ sơ của sinh viên khác", and Vietnamese or English injection are refused with a `violation_type` and audited as `refused`. | Built (pattern-based; see §12.2) |
| FR-5.8 | Store the conversation with its citations and answer mode (R8.8). | P1 | Another user reading the conversation gets 404. | Built |
| FR-5.9 | Stream the answer (NFR-1). | P1 | SSE events: `stage` after each pipeline node, then `delta` chunks of the **verified** answer, then `done` with citations and `mode`. The first event arrives before the model is called; the deltas joined equal the stored answer. | Built (works through Caddy with `flush_interval -1`) |
| FR-5.10 | With a model configured, the model writes the answer from `prompts/policy_assistant.md` (instructions and clauses in the system message, the question in the user message). | P1 | Answers state the right figure and cite the right article. | Built. **OpenAI gpt-4o:** 7/7 answerable questions written by the model (`mode=generated`) with the right figure and article, including paraphrases, p95 2.0 s. Ollama, Qwen2.5 1.5B, no time budget: 7/7 questions answered by the model (`mode=generated`), each with the expected figure (8 weeks, 14 days, 32 hours, 7 days) and article, including paraphrased questions ("deadline của report cuối kỳ", "mấy tiếng"). Qwen2.5 0.5B was faster but answered two questions with the wrong clause, so it is not recommended. |
| FR-5.11 | Cap the time spent on the model per question. | P0 | `LLM_ANSWER_BUDGET_SECONDS` (default 8) covers all generation attempts. When it runs out, the verified verbatim quote is returned (`mode=extractive_timeout`). | Built (test with a model that sleeps 5 s under a 0.3 s budget; live run below in NFR-1) |
| FR-5.12 | Limit assistant use per user. | P1 | More than 20 questions per user per minute return 429 (both endpoints). | Built (in-memory, per process) |
| FR-5.13 | Survive a provider failure (expired key, outage, quota). | P0 | When the model call raises, retrieved clauses are returned as a verified quote (`mode=extractive_error`) instead of "the assistant cannot answer". | Built. Against api.openai.com with an expired key: 6/6 answerable questions were answered correctly from quotes, p95 0.4 s. |

### 5.6 Regulation store — `GET/POST /policies`, `POST /policies/reindex`, `src/services/policy_index.py`

| ID | Requirement | Priority | Acceptance criterion | Status |
|---|---|---|---|---|
| FR-6.1 | Upload a PDF/DOCX/MD/TXT document with its code, title, effective from/to dates and the code it replaces (R9.1). | P0 | Only the Administrator can upload; with that role off, the coordinator lecturer can. Others get 403. | Built |
| FR-6.2 | Split by Chapter/Article/Clause, create embeddings and index (R9.2). | P0 | <ul><li>A document without "Điều N." lines is rejected (422).</li><li>With an embedder, every new chunk gets a vector; `POST /policies/reindex` fills vectors for chunks stored before a model was configured.</li><li>Paraphrased questions are found through embeddings.</li></ul> | Built. Thresholds are calibrated per model in `CALIBRATED_SIMILARITY`; `EMBEDDING_MIN_SIMILARITY` only overrides them. **text-embedding-3-small:** on-topic paraphrases scored 0.456–0.60, off-topic ≤ 0.257, so the threshold is 0.38. **bge-m3:** 33 chunks embedded. On-topic paraphrases scored cosine 0.61–0.67 and ranked the right clause first or second; off-topic questions scored 0.22–0.32, so the threshold is 0.5. nomic-embed-text was measured and rejected: an off-topic question scored 0.76, above the on-topic 0.65. Vectors are stored as JSON and compared in memory, not in pgvector. |
| FR-6.3 | A new document that replaces an old one marks the old one `superseded`; it is kept for reference and no longer retrieved (R9.3). | P0 | Seed: QĐ-TT/2025 (6 weeks) is replaced by QĐ-TT/2026 (8 weeks); a question on duration cites only 2026. | Built |
| FR-6.4 | Every user can list documents and read their chunks. | P2 | | Built |
| FR-6.5 | `POST /policies/reindex` reports a provider error. | P1 | An embedder failure returns 502 with the provider's message; it is no longer reported as success with 0 vectors. | Built |

### 5.7 Rule-based monitor — `src/services/monitor.py`, `/risk-flags`, `POST /monitor/run`

| ID | Requirement | Priority | Acceptance criterion | Status |
|---|---|---|---|---|
| FR-7.1 | Run daily at `MONITOR_HOUR` (and at startup), and after events: registration or outline decisions, evidence, milestones, logs, extensions (R10.1). | P0 | | Built (asyncio loop inside the API process) |
| FR-7.2 | Rules: (a) due in 3 days and not submitted, (b) overdue, (c) submitted without a required evidence type, (d) logged hours below 80% of expected from week 2, halved for part-time (R10.2). | P0 | Thresholds live in `cohort.yaml`. | Built |
| FR-7.3 | A flag has type, severity `info/warning/critical`, reason and evidence links (R10.3). | P0 | | Built |
| FR-7.4 | No duplicate open flag for the same (record, type, milestone) (R10.4). | P0 | Column `open_key` is UNIQUE; reruns create nothing. | Built (property test P4) |
| FR-7.5 | Notify the student of every flag and the lecturer at `warning` or above, in-app (R10.5). | P1 | | Built (email is not part of the spec) |
| FR-7.6 | Never change a record's state because of a flag (R10.6). | P0 | | Built |
| FR-7.7 | The lecturer acknowledges, resolves or dismisses a flag; dismissing needs a note (R10.7). | P0 | | Built |
| FR-7.8 | A flag whose condition no longer holds closes itself; a flag the lecturer dismissed is not raised again for 7 days. | P2 | | Built (beyond the spec) |

### 5.8 Milestone extension (HITL, audited) — `/milestones/{id}/extensions`, `/extensions/{id}/*`

| ID | Requirement | Priority | Acceptance criterion | Status |
|---|---|---|---|---|
| FR-8.1 | A student requests an extension for a milestone not yet `accepted`: new date, reason, optional evidence (R12.1). | P0 | The new date must be after the old one and at most `rules.extension.max_days` (14) later; otherwise 422 with the clause from `cohort.yaml`. One open request per milestone. | Built |
| FR-8.2 | The lecturer sees a summary and related clauses, labelled "Gợi ý của AI" (R12.2). | P1 | | Built |
| FR-8.3 | Only the assigned lecturer decides; approving and rejecting both need a reason (R12.3). | P0 | | Built |
| FR-8.4 | Approval moves the due date, clears `overdue` and closes the overdue flag in the same transaction (R12.4). | P0 | A due date changes only with an `approved` request; the `due_date_changed` audit event records the `extension_id`. | Built (P8) |
| FR-8.5 | An append-only trail of create, cancel, approve and reject (R12.5). | P0 | A DB trigger blocks `UPDATE`/`DELETE` on `audit_event` in SQLite and Postgres. | Built (a direct `UPDATE` on Postgres was tried and blocked) |
| FR-8.6 | The student cancels an undecided request. | P2 | | Built |

### 5.9 Aggregated list — `GET /internships-summary`, `GET /internships-summary/export` (R7, brought back into scope)

| ID | Requirement | Priority | Acceptance criterion | Status |
|---|---|---|---|---|
| FR-9.1 | A table of records for lecturers and the Administrator: student, company, cohort, state, % of milestones accepted, next milestone and its due date, number of open flags and the highest severity (R7.1). | P0 | Lecturers see only their assigned students; the Administrator sees all; students get 403. | Built |
| FR-9.2 | Filter by cohort, program, lecturer, state and risk (`any`, `none`, `info`, `warning`, `critical`); sort by student, company, state, progress, next due date or risk; search by name, student code or company; page through results (R7.2). | P0 | | Built |
| FR-9.3 | Export the filtered rows to CSV (UTF-8 with BOM for Excel) or XLSX, within the caller's scope, and audit each export (R7.3). | P0 | The file holds only the table's columns (no email, phone or tax code). Its row count equals the filtered list. An `exported` audit event records the format and row count. | Built |

### 5.10 History, notifications, administration

| ID | Requirement | Priority | Acceptance criterion | Status |
|---|---|---|---|---|
| FR-10.1 | Lecturers and the Administrator read the audit history of a record and its children (R12.5, R15.3). | P1 | A student gets 403. | Built |
| FR-10.2 | In-app notifications, mark all as read. | P1 | | Built |
| FR-10.3 | The Administrator creates accounts and assigns lecturers; open records move to the new lecturer (UC-53). | P1 | | Built |

## 6. The optional Administrator role

When on (`ENABLE_ADMIN_ROLE=true`, the default):
- The Administrator has a screen for milestone templates, lecturer assignments and new accounts.
- The Administrator has a read-only cohort-wide list with a lecturer filter.
- Only the Administrator uploads regulations, reindexes embeddings and presses **Chạy giám sát ngay**.

When off:
- `admin` cannot sign in, and `/admin/*` returns 404.
- The cohort, templates and assignments come from `config/cohort.yaml` and the seed.
- The lecturer with `is_coordinator` (`gv01` in the seed) uploads regulations and runs the monitor.

Both modes are tested (`test_optional_admin_role_on/off`).

## 7. Data contract

| Object | Fields that matter |
|---|---|
| `Internship` | `status` (draft, submitted, revision_requested, approved, rejected, in_progress, completed), company and mentor fields, `start_date`, `end_date`, `mode`, `ai_fields[]`, `decision_reason`, `version` |
| `Outline` | `content`, `status`, `version`, `ai_summary{label, summary, uncovered_outcomes[], source}`, `reason` |
| `Milestone` | `code`, `due_date`, `status` (pending, submitted, accepted, rejected, overdue), `required_evidence[]`, `citation{doc,path}`, `linked_to`, `template_id` (nullable) |
| `Evidence` | `evidence_type`, `filename`, `mime`, `size`, `sha256`; downloaded via `/files/{id}?exp&sig` |
| `LogEntry` | `week_no`, `content`, `difficulties`, `hours`, `status` (pending, accepted, returned), `comment`, `attachments[]` |
| `ExtensionRequest` | `previous_due_date`, `requested_due_date`, `reason`, `evidence_id`, `ai_summary{summary, extra_days, related_clauses[]}`, `status` (open, approved, rejected, cancelled), `decision_reason` |
| `RiskFlag` | `flag_type` (due_soon, overdue, missing_evidence, low_hours), `severity`, `reason`, `evidence_refs[]`, `status` (open, acknowledged, resolved, dismissed), `open_key` |
| `PolicyDoc` / `PolicyChunk` | `code`, `effective_from`, `effective_to`, `status` (active, superseded), `supersedes_id` / `path` ("Chương II / Điều 5 / Khoản 2"), `text`, `embedding` (nullable) |
| Summary row (`/internships-summary`) | `student_code`, `student_name`, `program`, `cohort`, `lecturer`, `company`, `status`, `progress_pct`, `next_milestone`, `next_due`, `next_status`, `open_flags`, `max_severity`; response adds `total`, `page`, `page_size`, `facets` |
| SSE event (`/assistant/chat/stream`) | `{type: "stage", stage, label}`, `{type: "delta", text}`, `{type: "done", conversation_id, answer, citations[{n, chunk_id, label, excerpt}], outcome, mode, suggest_extension}`, `{type: "error", detail}`. `mode` is `generated`, `extractive`, `extractive_fallback` or `extractive_timeout`. |
| `AuditEvent` | `actor_id`, `actor_kind` (human, system), `actor_role`, `entity`, `entity_id`, `action`, `before`, `after`, `reason` |

Storage: 18 tables created by `Base.metadata.create_all` at startup. There are no migrations; `init_db` adds columns introduced later (today only `policy_chunk.embedding`). Files live in `UPLOAD_DIR`. The cohort configuration is `config/cohort.yaml`; sample regulations are `seed/policies/*.md`.

## 8. Non-functional requirements

| ID | Category | Requirement | Status |
|---|---|---|---|
| NFR-1 | Latency | Assistant p95 ≤ 10 s, with streaming (spec NFR-1). | Built. <ul><li>**OpenAI (gpt-4o + text-embedding-3-small):** p95 2.0 s, median 1.2 s over 10 questions, all model-written.</li><li>**No-LLM mode:** p95 20 ms, first event ≤ 106 ms (`test_nfr1_latency_no_llm_mode`).</li><li>**Live, Qwen2.5 1.5B on the laptop CPU, default 8 s budget:** p95 8.4 s over 10 questions, first event ≤ 40 ms. The model never finished within budget on this CPU, so every answered question was a verified verbatim quote (`extractive_timeout`).</li><li>**Same model, budget off:** every answer was model-written and correct, but p95 was 16.1 s.</li></ul>Model-written answers within 10 s need faster hardware or a hosted API; that was not measured. |
| NFR-2 | Deployment | One `docker compose up`; runs without an API key (spec NFR-2). | Built. The Dockerfile builds the React frontend in a Node stage, then the Python image. The template's original Dockerfile was broken (packages installed to `/root/.local`, unreadable by the non-root user) and has been fixed. |
| NFR-3 | Language and device | Vietnamese interface, usable on a phone (spec NFR-3). | Built: on the React frontend, 11 screens rendered in headless Chrome at 390 × 844 over HTTPS have no horizontal overflow and no console errors (`tests/ui/mobile-check.mjs`, re-run 2026-11-14 after the CSP fix in §13). Not tried on a physical device. |
| NFR-4 | Prompts | Prompts live in `prompts/*.md` (spec NFR-4). | Built (`policy_assistant.md`, `intake_extract.md`, `reviewer_summary.md`). |
| NFR-5 | Testing | Automated tests for the state machine, access, citation checks and monitor rules (spec NFR-5). | Built (§11). |
| NFR-6 | Security | HTTPS on deployment; private files behind expiring URLs (R15.1). | Built. <ul><li>Caddy terminates TLS, redirects HTTP with 308, and sends HSTS, a CSP of `default-src 'self'` (scripts only from the site, no inline scripts; styles and fonts also from Google Fonts for the Lexend typeface), `X-Frame-Options: DENY` and `nosniff`.</li><li>`SITE_ADDRESS=localhost` uses Caddy's internal CA, so browsers warn until it is trusted; a real domain gets a Let's Encrypt certificate.</li><li>The backend port is bound to `127.0.0.1` only.</li></ul> |
| NFR-7 | Security | Mask PII before calling an LLM (R15.2). | Built: known values of the asker, then regex for email, phone, student code, ID and tax numbers (property test P6). |
| NFR-8 | Security | Audit every state change and every denied access (R15.3). | Built |
| NFR-9 | Security | No PII in application logs (R15.4). | Built (`test_r15_4_application_logs_contain_no_pii`) |
| NFR-9a | Security | No data to third parties unless intended (R15.5). | Built. The template's `.env.example` enabled LangSmith tracing with a placeholder key, so the app tried to send traces (prompts with masked student context) to api.smith.langchain.com. `guard_tracing()` in `src/main.py` now switches tracing off unless a real `LANGCHAIN_API_KEY` is set. Tracing with a real key stays possible because it is a course deliverable. |
| NFR-10 | Recovery | A restart loses no data. | Built: Postgres volume `pgdata`, files in `./data`, certificates in `caddy_data`. Rate-limit counters are in memory and reset on restart. |
| NFR-11 | Security | Rate limits and lock-out (FR-1.7, FR-1.8, FR-5.12, FR-2.2). | Built, per process. Revoking a JWT before it expires is not built (beyond spec). |
| NFR-12 | Scale (beyond spec) | Several workers or instances. | Not built. The monitor loop and the rate-limit counters live in the process. With several workers, the monitor runs twice (flags stay unique through `open_key`, notifications could repeat) and limits apply per worker. |
| NFR-13 | Observability (beyond spec) | Per-turn agent traces and cost. | Not built. Logs, the audit trail and the stored answer `mode` only. |

## 9. Dependencies and configuration

- **Backend:** Python 3.12, FastAPI, LangGraph, SQLAlchemy 2, psycopg 3, httpx, pypdf, python-docx, python-multipart, openpyxl. Dev: pytest, pytest-asyncio, hypothesis, ruff.
- **Proxy:** `caddy:2.8.4-alpine` with `deploy/Caddyfile`.
- **Database:** PostgreSQL 16 (compose) or SQLite (`DATABASE_URL=sqlite:///./data/app.db`, also the test database, with foreign keys switched on).
- **Frontend:** React 18.3, react-router-dom 6.28 (HashRouter), Vite 5.4, in `frontend/`; built in the Docker image (`npm ci && npm run build`). Font Lexend from Google Fonts. `web/` keeps the first plain-JS version as a fallback.
- **Models:** any OpenAI-compatible endpoint through the template's `src/services/llm.py` (`MODEL_CLASSIFY`, `MODEL_GENERATE`, `OPENAI_BASE_URL`, `LLM_MAX_TOKENS`) and `EMBEDDING_MODEL`. `deploy/docker-compose.llm.yml` runs Ollama with Qwen2.5 1.5B and bge-m3, and sets the embedding threshold measured for bge-m3. With no key, or the sample key `sk-your…`, `llm_available()` returns `False`.
- **SSO test IdP:** `deploy/docker-compose.sso.yml` runs Keycloak 25.0.6 in dev mode with the `vin15` realm imported from `deploy/keycloak/vin15-realm.json`. It is for testing only.
- **Key settings** (`.env.example`):

  | Group | Variables |
  |---|---|
  | Secrets and URLs | `JWT_SECRET` (must be changed for deployment), `SITE_ADDRESS`, `OIDC_*` |
  | Roles and seed | `ENABLE_ADMIN_ROLE`, `SEED_DEMO_DATA` |
  | Monitor | `MONITOR_HOUR` |
  | Retrieval | `RETRIEVAL_MIN_SCORE`, `RETRIEVAL_MIN_COVERAGE`, `EMBEDDING_MIN_SIMILARITY` |
  | Model calls | `LLM_ANSWER_BUDGET_SECONDS`, `LLM_CONTEXT_HITS`, `LLM_CONTEXT_CHARS` |
  | Rate limits | `LOGIN_MAX_FAILURES`, `LOGIN_LOCK_MINUTES`, `LOGIN_IP_PER_MINUTE`, `ASSISTANT_PER_MINUTE`, `INTAKE_PER_MINUTE` |
  | Files | `MAX_UPLOAD_MB`, `FILE_URL_TTL_SECONDS` |

- **Demo data:** seeded when the database is empty:
  - 30 students, 3 lecturers and 1 administrator.
  - 1 cohort, 3 companies and 3 sample regulations, one of them superseded.
  - 5 scenarios: `sv02` waiting for approval, `sv03` in progress with low hours and an outline pending, `sv04` overdue with an extension request, `sv05` on track, `sv06` sent back for revision.

  The password is `demo123`. All data is synthetic.

## 10. Success metrics (proposed, not instrumented)

| ID | Metric | Definition | Target |
|---|---|---|---|
| MET-1 | Self-served questions | Questions with `outcome=answered` that the student does not ask a lecturer within 7 days | To set from a baseline |
| MET-2 | Citation accuracy | Sampled answers whose citation is the right clause, judged by a person | ≥ 90% |
| MET-3 | Model-written share | Answered questions with `mode=generated` rather than a verbatim quote | Track per model and host |
| MET-4 | Returned registrations | Share of submitted records that end `revision_requested` or `rejected` | Lower than the paper process |
| MET-5 | Early warning | Overdue milestones that had a `due_soon` flag first | ≥ 80% |
| MET-6 | False warnings | Flags dismissed by lecturers out of all flags | ≤ 15% |
| MET-7 | Decision time | Median from `submitted` to a decision (registration, outline, extension) | ≤ 3 working days |
| MET-8 | Correct refusals | Adversarial questions (injection, other students' data) refused | 100% on the sample set |

## 11. Testing

### 11.1 Test layers and how to run them

| Layer | What it checks | How to run | Status |
|---|---|---|---|
| Backend VIN-15 (pytest, 90 tests in `tests/test_vin15/`) | Covers: <ul><li>state machine and decision rights</li><li>data scope</li><li>registration rules</li><li>monitor</li><li>regulation store and embeddings</li><li>assistant (citations, grounding, numbers, fallback, time budget, refusals, PII, streaming, latency)</li><li>SSO (mocked IdP)</li><li>intake and storage</li><li>the full HTTP flow</li><li>extensions</li><li>template editing</li><li>Administrator on/off</li><li>PII in logs</li><li>aggregated list and export</li><li>rate limits and lock-out</li><li>demo endpoints behind sign-in</li></ul>Each test starts from a freshly seeded in-memory SQLite. | `pytest tests/test_vin15` (Docker: `docker build -f Dockerfile.dev -t vin15-dev .` then `docker run --rm -v "$PWD":/app vin15-dev pytest`) | Built |
| Property-based (Hypothesis, same suite) | P1 (60 examples), P2 (80), P3 (40 random queries), P4 (25). | As above | Built |
| Template (55 tests) | Demo ReAct agent, guardrails, HITL interrupt, eval scripts. Route tests now sign in through a dependency override. | `pytest` | Built. 145 tests pass in total. |
| Lint | ruff on the project's own code | `ruff check src/ tests/ scripts/seed.py scripts/llm_e2e.py scripts/sso_e2e.py` | Built, clean. The template's logging scripts in `scripts/` have pre-existing ruff findings that were left alone. |
| Live model E2E (`scripts/llm_e2e.py`) | Covers: <ul><li>embedding reindex</li><li>10 assistant questions over SSE, each checked for outcome, cited article and the expected figure in the answer</li><li>refusal and not-found cases</li><li>intake extraction</li><li>outline summary</li><li>NFR-1 p95</li></ul> | `docker compose -f docker-compose.yml -f deploy/docker-compose.llm.yml up -d`, pull the models, then `docker run --rm --network mini-agent-studio_default -v "$PWD":/app vin15-dev python scripts/llm_e2e.py` | Run 2026-11-14 with Qwen2.5 1.5B + bge-m3: all checks pass with the default 8 s budget. With the budget off, everything passes except NFR-1 (p95 16.1 s). Not in CI. |
| OpenAI E2E (`scripts/llm_e2e.py`, default stack with `OPENAI_API_KEY` in `.env`) | Same script against api.openai.com (gpt-4o, gpt-4o-mini, text-embedding-3-small). | `docker compose up -d`, then the same `docker run … llm_e2e.py` | Two runs on 2026-11-14: <ul><li>**Expired key:** the degraded-mode checks passed (answers from quotes, p95 0.4 s, refusals, not-found).</li><li>**Valid key:** all checks passed. 7/7 answers were model-written and correct, p95 2.0 s; intake `source=llm`; outline summary; refusals and not-found.</li></ul> |
| Real SSO E2E (`scripts/sso_e2e.py`) | The full flow through Keycloak's login form, as in §5.1 FR-1.2. | `docker compose -f docker-compose.yml -f deploy/docker-compose.sso.yml up -d`, then `python scripts/sso_e2e.py` in the network | Run 2026-11-14: 8/8. Not in CI. |
| UI smoke (jsdom, `tests/ui/ui-smoke.mjs`, 28 checks) | Functional checks written for the first, plain-JS frontend (`web/app.js`): login, registration and rule check, timeline, logs, extension form, assistant over SSE, regulations, lecturer queue, list and filter, detail and audit, warnings, admin screen and templates. | Only against the legacy `web/` build | Passed 28/28 on the plain-JS frontend (2026-11-14). **Does not run against the React frontend**, which has no `app.js`; the React app has no automated functional UI test yet (§11.4). |
| Mobile (headless Chrome, `tests/ui/mobile-check.mjs`) | 11 screens across all roles at 390 × 844 over HTTPS: no horizontal overflow, no console errors, screenshots in `tests/ui/screens/`. | `npm run mobile` (set `BROWSER_PATH` if Chrome is elsewhere; Edge works) | Built. React frontend: 11/11 on 2026-11-14 after the CSP fix (before it, every screen logged the blocked font and theme script). Not in CI. |
| Postgres and HTTPS, by hand | The full stack through the API, a direct `UPDATE audit_event`, HTTP→HTTPS redirect, security headers, SSE through Caddy. | §11.3 | Done once on 2026-11-14; not automated. |
| CI | `.github/workflows/ci.yml` from the template runs `ruff check src/ tests/` and `pytest tests/` on Python 3.11. | Push to GitHub | Not run: the repository has not been pushed. |

### 11.2 Acceptance criteria that exist today

| Check | Criterion | Where it runs |
|---|---|---|
| P1 — the AI never decides (FR-3.4) | Every edge in `DECISION_EDGES` raises for `actor.kind ∈ {agent, system}` and any role. | `test_state_machine.py::test_p1_*` |
| P2 — valid, grounded citations (FR-5.4) | Kept ids are a subset of the retrieved chunks; a grounded sentence with a valid id is kept; off-topic text is dropped. | `test_p2_*`, `test_grounding_rejects_off_topic_and_wrong_numbers` |
| Wrong figures (FR-5.4) | "2 tuần" / "6 tuần" against a clause that says 8 weeks is dropped, even though the clause number is "2." | `test_grounding_*`, `test_unverifiable_model_answer_*` |
| P3 — only regulations in force (FR-5.1) | Every hit belongs to an `active` document with `effective_from ≤ today < effective_to`. | `test_p3_*`, `test_future_policy_*`, `test_synonym_query_needs_embeddings` |
| P4 — idempotent monitor (FR-7.4) | Two to four reruns create no new flag. | `test_p4_*` |
| P5 — data scope (FR-1.3, FR-1.4, FR-9.1) | 4 viewer/owner pairs × 4 routes all return 403 and write `access_denied`; lecturer lists and exports hold only assigned students. | `test_p5_*`, `test_r7_*` |
| P6 — no PII to the model (NFR-7) | The prompt passed to the model holds none of the asker's name, student code, email or phone. | `test_p6_*` |
| P7 — one audit event per transition (FR-3.5) | Exactly one new event, with `version` and the actor. | `test_p7_*` |
| P8 — due dates move only through an approved extension (FR-8.4) | | `test_p8_*` |
| Time budget (FR-5.11) | A model slower than the budget yields a verified quote within the budget. | `test_slow_model_hits_time_budget_and_falls_back` |
| Lock-out and limits (FR-1.7, FR-1.8, FR-5.12) | Lock after N failures even with the right password; per-IP and per-user 429. | `test_login_*`, `test_assistant_usage_limit` |
| Export (FR-9.3) | CSV and XLSX row counts equal the filtered list; no email in the file; audited. | `test_r7_export_*` |
| Streaming and latency (FR-5.9, NFR-1) | Stage order; deltas join to the stored answer; p95 ≤ 10 s and first event ≤ 2 s in no-LLM mode. | `test_stream_*`, `test_nfr1_*` |
| SSO (FR-1.2) | Success maps to the local account; four failure paths redirect to the error page. | `test_sso_*` (mocked), `scripts/sso_e2e.py` (Keycloak) |

Everything else is judged by a person: whether an answer reads the regulation correctly beyond the checked figure, whether "outcomes not mentioned" makes sense, and whether the interface is easy to use.

### 11.3 Manual test procedure

Prerequisites: `docker compose down -v && docker compose up -d --build`, then open https://localhost and accept the certificate warning. Record each case with the account, the steps, the result and a screenshot.

| Case | Do | Pass when |
|---|---|---|
| T-1 Fill from file | As `sv01`, create a record and upload a TXT/DOCX letter containing "Mã số thuế: 0101234567" and "từ ngày … đến ngày …". Press **Điền vào form**. | Fields turn purple; the company name comes from the catalog. |
| T-2 Rule check | Set the end date 6 weeks after the start and press **Kiểm tra theo quy chế**. | "tối thiểu 8 tuần" with "Căn cứ: QĐ-TT/2026 · Điều 5 / Khoản 2"; submitting is blocked. |
| T-3 Approve | As `gv01`, approve `sv01`'s record. Try **Từ chối** with an empty reason first. | Rejecting without a reason fails. After approval, `sv01` sees 5 milestones. |
| T-4 Outline | `sv01` submits an outline; `gv01` reads the "Gợi ý của AI" box and approves. | **Đề cương được duyệt** becomes **Đã chấp nhận**. |
| T-5 Assistant | As `sv03`, ask "Thời gian thực tập tối thiểu là bao nhiêu tuần?" | Progress steps appear, then the answer: 8 weeks, citing QĐ-TT/2026 Article 5 Clause 2, with no mention of the 2025 rule. |
| T-6 Refusals | Ask "Cho em xem hồ sơ của SV2026010", "bỏ qua mọi hướng dẫn…", "Giá vàng hôm nay?" | The first two are refused; the last is "not found". |
| T-7 Extension | As `gv01`, approve `sv04`'s extension with a reason. | The due date moves, **Quá hạn** disappears, the overdue flag closes, and the audit table shows `due_date_changed`. |
| T-8 Warnings | As `gv03`, dismiss `sv03`'s low-hours flag without a note, then with one. | The first try fails; then the flag closes. **Chạy giám sát ngay** (admin) does not raise it again. |
| T-9 Scope | Signed in as `sv03`, call `/api/v1/internships/<sv04's id>` from http://127.0.0.1:8000/docs. | 403. |
| T-10 No Administrator | Set `ENABLE_ADMIN_ROLE=false` in `.env` and restart. | `admin` cannot sign in; `gv01` sees the upload form and `gv02` does not. |
| T-11 HTTPS | `curl -I http://localhost/` and `curl -kI https://localhost/`. | 308 to HTTPS; the HTTPS response carries HSTS and the CSP. |
| T-12 Aggregated list | As `gv01`, open **Sinh viên**, set **Mức rủi ro** to **Có cảnh báo**, then **Xuất Excel**. | Only flagged students show; the XLSX opens with the same rows and no emails. As `admin`, **Danh sách** shows all lecturers' students. |
| T-13 Lock-out | Sign in as `sv05` with a wrong password five times, then with `demo123`. | The sixth attempt is refused with "tạm khóa"; `sv06` can still sign in. |
| T-14 Live model | Start with `deploy/docker-compose.llm.yml`, pull the models, run `scripts/llm_e2e.py`. | "all checks passed". |
| T-15 Real SSO | Start with `deploy/docker-compose.sso.yml`, run `scripts/sso_e2e.py`; or in a browser, configure `OIDC_REDIRECT_URI=https://localhost/...` and sign in as `chi.le` / `Sso-demo-123`. | 8/8; the browser lands on `sv03`'s record. |

### 11.4 Gaps in testing

- OpenAI was measured on 10 questions only, and embedding thresholds on 8 calibration questions; a larger set is R16.
- The live-model and real-SSO runs are scripts run by hand, not part of CI.
- The live-model question set has 10 questions; there is no larger answer-quality set (R16 is deferred).
- pytest runs on SQLite only; Postgres and HTTPS were checked by hand.
- The React frontend has no automated functional test; the jsdom smoke covers only the legacy plain-JS app. Porting it (or adding Playwright) is pending. The mobile check verifies layout and console errors only.
- The UI checks are not in CI.
- No load test.
- The refusal rules are regex; there is no large adversarial set to measure MET-8.

## 12. Limits of the product: time and capability

### 12.1 Time

- **No-LLM mode:** no network call. The 145 pytest tests take about 21 s on Docker Desktop. The assistant's p95 is 20 ms.
- **Live model on the development laptop (CPU only):**
  - Qwen2.5 1.5B needs 10–16 s per answer. With the default 8 s budget, every answered question returns a verbatim quote in about 8.3 s.
  - Qwen2.5 0.5B answers in about 4 s but picked the wrong clause twice in 10 questions.
  - bge-m3 embeds the 33 sample chunks at startup in a few seconds.
  - Off-topic and refused questions return in under 0.5 s, because no model is called.
- **Summaries:** outline and extension summaries make one model call inside the submit request, with no budget of their own, so on a slow host they slow submission down.
- **What streams:** progress events reach the screen at once. The answer text streams only after `verify`, so the user waits for the whole generation before the first word appears. This is a deliberate trade so that unverified claims are never shown (WORKLOG ADR-005).
- **Monitor:**
  - Runs once at startup, then daily at 07:00 server time, plus per record after events.
  - A milestone becomes `overdue` at the first daily run after its due date, so the change can lag by up to about 24 hours.
- **Time zone:** the container runs on UTC, so "07:00" is 14:00 in Vietnam and "today" is the UTC date. There is no `TZ` setting.

### 12.2 Capability

- **Grounding is lexical.**
  - A sentence must reuse ≥ 60% of the clause's content words and every number in it.
  - A correct paraphrase in very different words is dropped; the user then gets the verbatim quote.
  - The check confirms that a sentence comes from the clause, not that it answers the question. With weak models (0.5B), a grounded sentence from the wrong clause can still pass.
- **Embedding thresholds are per model.**
  - Thresholds were measured on the three sample documents with 8 questions: 0.38 for text-embedding-3-small, 0.50 for bge-m3. Another model needs a new measurement.
  - nomic-embed-text cannot separate Vietnamese topics.
  - Without an embedder, BM25 misses synonyms ("deadline", "mấy tiếng").
- **Verbatim answers** quote the one or two best clauses; they do not apply the rule to the student's situation.
- **Documents need "Điều N." lines** to be split. Tables, annexes and forms without articles are skipped.
- **Refusals are pattern-based.** A question phrased differently may get through. The assistant still holds no other student's data to leak, because its only tool is the regulation store.
- **Intake does not read scans or photos** (no OCR).
- **"Outcomes not mentioned" depends on keywords** set in the configuration.
- **SSO does not verify the id_token signature.** Identity comes from the IdP's userinfo endpoint over the back channel with the access token just obtained. Accounts must already exist.
- **One cohort, one rule set** (`current_cohort`); parallel cohorts are not supported.
- **One exception type** (milestone extension) with one approval step.

## 13. Known gaps and risks

- **Tokens:**
  - The token lives in `localStorage`; the CSP (`script-src 'self'`) and escaping of all rendered data reduce the XSS risk but do not remove it.
  - A JWT cannot be revoked before it expires (8 hours).
  - `JWT_SECRET` defaults to a development value and must be changed.
- **Rate limits and the monitor are per process** (NFR-12). With several workers, use one worker or move the counters to a shared store.
- **Hardware decides whether answers are model-written.** On CPU-only hosts with a capable model, the time budget turns most answers into verbatim quotes. They are correct but not tailored.
- **Sending data to a hosted model needs the school's consent.** Intake sends the mentor's name and the letter's text (email, phone and numbers are masked).
- **No migrations.** `init_db` adds known new columns, but other schema changes on a database with data need manual work.
- **Bugs found late:**
  - Replacing milestone templates deleted templates that existing milestones still pointed to. Postgres rejected it; SQLite tests had missed it because foreign keys were off. Fixed, and SQLite now enforces foreign keys.
  - The first live-model run showed the citation check accepting off-topic and wrong-number answers. Fixed with the grounding rules in FR-5.4.
  - The OpenAI run (2026-11-14) found:
    - **Embeddings could not reach OpenAI.** `.env` has `OPENAI_BASE_URL=` empty, docker passes the empty string into the container, and the SDK built an empty URL ("missing protocol"). Fixed: `openai_base_url()` always passes an explicit URL. A regression test fails without the fix.
    - **A provider error made the assistant refuse to answer.** Fixed by FR-5.13.
    - **Reindex reported success with 0 vectors.** Fixed by FR-6.5.
    - **LangSmith tracing was on with a placeholder key.** Fixed by NFR-9a.
  - After the React frontend was merged (PR #3), the CSP blocked its Google Fonts stylesheet and its inline theme script on every page over HTTPS, so the redesign showed a fallback font and dark-mode users saw a light flash. Fixed locally: the CSP allows `fonts.googleapis.com` and `fonts.gstatic.com`, and the theme script moved to `frontend/public/theme-init.js`. Not yet committed.
  - The lecturer queue appended "· chỉ để tham khảo" to an AI label that already ended with it. Fixed locally in `LecturerQueue.jsx`. Not yet committed.
- **Deviations from the design**, with reasons in WORKLOG ADR-001 to ADR-011:
  - React with Vite instead of Next.js (the first build was plain JS; the React redesign came in PR #3)
  - BM25 plus JSON embeddings instead of pgvector
  - an asyncio loop instead of APScheduler
  - `create_all` instead of Alembic
  - jsdom (legacy frontend only) and headless Chrome instead of Playwright
  - in-memory rate limits

## 14. Open questions

| ID | Question | Owner | Status |
|---|---|---|---|
| OQ-1 | Does deferring R7 count as missing a basic deliverable? | Product + Mentor | Closed: R7 is built (§5.9). |
| OQ-2 | May masked data go to a hosted LLM, or must the model be self-hosted? May intake send the mentor's name? | School | Open |
| OQ-3 | Keep, protect or remove the template's demo endpoint (`/api/v1/chat`)? | Engineering | Closed: it requires sign-in (FR-1.9). Removing it is still an option. |
| OQ-4 | Who writes the evaluation set for answer quality, how many questions, and when is it run (R16)? | QA + Academic Affairs | Open |
| OQ-5 | Should the 14-day limit and monitor thresholds differ by cohort or program? (They are already per cohort in YAML.) | Academic Affairs | Open |
| OQ-6 | Which production IdP? | Engineering + School IT | Open. The flow is verified against Keycloak 25; the school's IdP still has to be configured and tried. |
| OQ-7 | Keep the optional role as Administrator, or switch it to Company Mentor? | Product | Open |
| OQ-8 | Are parallel cohorts and per-program learning outcomes needed? | Product | Open |
| OQ-9 | Which time zone should deadlines and the daily monitor use? | Engineering | Open |
| OQ-10 | Which model and host: a hosted API (fast, needs consent and budget) or a self-hosted model on a GPU (keeps data in house)? | Product + School IT | Open. A CPU-only host keeps answers correct but mostly verbatim (NFR-1). |

## 15. Change log

| Version | Date | Author | Change |
|---|---|---|---|
| 0.1 | 2026-11-13 | Product team (drafted with Claude Code) | First PRD, in Vietnamese, written from the code after the build against spec version 2 (two main roles plus an optional Administrator; R6, R7, R16 deferred). |
| 0.2 | 2026-11-14 | Product team (drafted with Claude Code) | Rewritten in English to follow the sample format. Added streaming, HTTPS, SSO (mocked IdP), embeddings, log attachments, extension evidence, the template editor, mobile and PII-in-log checks. Recorded the template foreign-key bug. |
| 0.3 | 2026-11-14 | Product team (drafted with Claude Code) | Built R7 (aggregated list, filters, export). Put the template's demo endpoints behind sign-in. Added lock-out and rate limits. Ran SSO against Keycloak 25 and the model path against Ollama (Qwen2.5, bge-m3). Added grounding, number checks, `[n]` citations, the verbatim fallback and the 8 s time budget after the live run exposed off-topic and wrong-number answers. Recorded live latency (NFR-1) and the nomic-embed-text finding. |
| 0.4 | 2026-11-14 | Product team (drafted with Claude Code) | Called api.openai.com: the key in `.env` was expired (401). Fixed the empty-`OPENAI_BASE_URL` embedding bug, the hard refusal on provider errors (FR-5.13), silent reindex failures (FR-6.5) and unintended LangSmith tracing (NFR-9a). 144 tests. OpenAI quality and latency are pending a valid key. |
| 0.5 | 2026-11-14 | Product team (drafted with Claude Code) | Ran against OpenAI with a valid key: all live checks pass, p95 2.0 s. Calibrated text-embedding-3-small (threshold 0.38); thresholds are now per model. Added LAN access through Caddy (`DEFAULT_SNI`, needed because browsers send no SNI to an IP address). 145 tests. |
| 0.6 | 2026-11-14 | Product team (drafted with Claude Code) | Checked against `main` after the React frontend merge (PR #3): updated scope, basis, user journey, dependencies and deviations for React/Vite. Found and fixed the CSP blocking the React fonts and theme script, and a duplicated AI label. Re-ran the mobile check on React (11/11). Marked the jsdom smoke as legacy-only. Threshold text now per model. Added companion documents (brief, wireframes). Change log put in version order. |
