# Worklog — VIN-15 Hệ thống hỗ trợ thực tập bằng AI

> Ghi lại công việc theo ngày và các quyết định kỹ thuật (ADR).

---

## 2026-11-13

| Member | Task | Status | Output | Time |
|--------|------|--------|--------|------|
| Claude Code | Spec Kiro (requirements, design, tasks, use cases), thu hẹp phạm vi còn 2 vai trò + QTV tùy chọn | ✅ Done | `.kiro/specs/internship-ai-assistant/` | |
| Claude Code | Backend, giao diện, seed, test; sửa Dockerfile gốc | ✅ Done | `src/`, `web/`, `tests/test_vin15/` | |
| Claude Code | PRD bản đầu | ✅ Done | `PRD.md` | |

**Tổng kết ngày:** vòng lõi SV–GV chạy được trên Postgres; 109 test pass.

---

## 2026-11-14

| Member | Task | Status | Output | Time |
|--------|------|--------|--------|------|
| Claude Code | Streaming SSE, HTTPS (Caddy), SSO/OIDC, embedding, UI còn thiếu, kiểm tra mobile | ✅ Done | 124 test pass; UI smoke 26/26; mobile 10/10 | |
| Claude Code | Sửa lỗi xóa mẫu mốc vi phạm khóa ngoại (lộ ra trên Postgres); bật khóa ngoại cho SQLite trong test | ✅ Done | `admin_routes.py`, `db.py` | |
| Claude Code | PRD viết lại bằng tiếng Anh theo mẫu | ✅ Done | `PRD.md` | |
| Claude Code | R7 danh sách tổng hợp + xuất CSV/XLSX; khóa endpoint demo; giới hạn tần suất | ✅ Done | `summary_routes.py`, `ratelimit.py` | |
| Claude Code | Chạy đường LLM thật (Ollama) và SSO thật (Keycloak); sửa các lỗi chỉ lộ ra với model thật | ✅ Done | `scripts/llm_e2e.py`, `scripts/sso_e2e.py`; 140 test pass | |

---

## ADR

**[ADR-001] Pipeline tuyến tính cho trợ lý chính sách**
- Context: template có ReAct loop; trợ lý chỉ có một nguồn (kho quy định) và không có tool ghi.
- Options: ReAct với tool `search_policy`; pipeline cố định.
- Decision: pipeline `guard → retrieve → synthesize → verify → finalize`.
- Consequences: ít lời gọi LLM, dễ kiểm chứng trích dẫn; muốn thêm nguồn dữ liệu sẽ phải thêm node.

**[ADR-002] Quyết định HITL enforce ở `transition()`, không ở prompt**
- Context: đề yêu cầu mọi phê duyệt do người thật.
- Decision: một hàm duy nhất đổi trạng thái; cạnh quyết định chỉ cho `actor.kind="human"`, vai trò GV, đúng GV phụ trách.
- Consequences: AI/system không thể duyệt dù prompt bị vượt; mọi đường đổi trạng thái mới phải đi qua hàm này.

**[ADR-003] Giao diện SPA JS thuần thay Next.js**
- Context: design ghi Next.js; image không có Node; giao diện là vài màn hình CRUD.
- Decision: `web/` tĩnh do FastAPI phục vụ.
- Consequences: không build, deploy một image; không có component library, test UI bằng jsdom + Chrome headless.

**[ADR-004] Truy hồi BM25 + embedding JSON thay pgvector**
- Context: kho quy định vài trăm đoạn; không có API key thì không có embedding.
- Decision: BM25 giữ dấu luôn chạy; khi có key, vector lưu JSON và so cosine trong RAM.
- Consequences: chạy được offline; kho lớn (hàng chục nghìn đoạn) sẽ cần pgvector.

**[ADR-005] Stream sau khi kiểm chứng**
- Context: NFR-1 cần streaming; R8.4 cấm hiển thị khẳng định không có nguồn.
- Decision: SSE gửi tiến độ từng bước ngay, câu trả lời chỉ stream sau `verify`.
- Consequences: sự kiện đầu đến nhanh; chữ của câu trả lời không hiện dần trong lúc LLM đang sinh.

**[ADR-006] HTTPS bằng Caddy**
- Decision: thêm service `proxy` (Caddy) với chứng chỉ tự động, header bảo mật.
- Consequences: localhost dùng CA nội bộ (trình duyệt cảnh báo); tên miền thật lấy Let's Encrypt.

**[ADR-007] SSO khớp tài khoản nội bộ, không tin claim vai trò**
- Decision: OIDC chỉ xác thực danh tính; vai trò và phân công lấy từ DB của hệ thống.
- Consequences: nhà trường phải tạo tài khoản trước (không tự cấp); không xác thực chữ ký id_token, danh tính lấy từ userinfo của IdP qua TLS.

**[ADR-008] Kiểm tra bám nguồn từng câu (grounding), không chỉ kiểm tra số trích dẫn**
- Context: chạy với model thật (Qwen2.5 1.5B), model gắn [1] vào câu trả lời cho câu hỏi khác, hoặc viết "2 tuần" khi quy định ghi 8 tuần; kiểm tra cũ chỉ xét id trích dẫn hợp lệ nên cho qua.
- Decision: mỗi câu phải có ≥ 4 từ, ≥ 60% từ nội dung có trong đoạn được trích, và MỌI con số trong câu phải có trong thân đoạn (bỏ tiêu đề Điều và số thứ tự khoản). Câu đúng nhưng thiếu trích dẫn được gắn vào đoạn nó bám.
- Consequences: chặn được sai số liệu và trích dẫn lạc đề; câu diễn giải quá xa văn bản có thể bị loại (khi đó trả trích dẫn nguyên văn).

**[ADR-009] Ngân sách thời gian 8 s cho model, quá hạn thì trích nguyên văn**
- Context: NFR-1 (p95 ≤ 10 s). Model 1.5B chạy CPU mất 10–16 s; tốc độ phụ thuộc phần cứng/nhà cung cấp.
- Decision: `LLM_ANSWER_BUDGET_SECONDS=8` cho mọi lần sinh của một câu hỏi; hết hạn → trả đoạn quy định đã kiểm chứng, `mode=extractive_timeout`, giao diện ghi "Trích nguyên văn".
- Consequences: p95 luôn ≤ ~8.5 s và không bao giờ trả câu sai nguồn; trên phần cứng chậm, người dùng nhận trích dẫn thay vì câu diễn giải.

**[ADR-010] Ngưỡng embedding phải hiệu chỉnh theo model**
- Context: nomic-embed-text cho câu lạc đề ("Thủ đô của Pháp") cosine 0.76, cao hơn câu đúng chủ đề (0.65) — không dùng được cho tiếng Việt. bge-m3: đúng chủ đề 0.61–0.67, lạc đề 0.22–0.32.
- Decision: dùng bge-m3 với ngưỡng 0.5 trong cấu hình Ollama; ghi rõ ngưỡng là theo model.
- Consequences: đổi model embedding phải đo lại ngưỡng trên kho quy định trước khi bật.

**[ADR-011] Giới hạn tần suất trong bộ nhớ**
- Decision: cửa sổ trượt trong process cho đăng nhập (theo tài khoản và IP) và cho trợ lý/intake (theo người dùng).
- Consequences: đủ cho một instance; chạy nhiều worker/instance cần Redis hoặc proxy làm việc này.
