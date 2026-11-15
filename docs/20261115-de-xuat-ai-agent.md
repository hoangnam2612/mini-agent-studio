# Đề xuất bổ sung: nâng cấp AI Agent cho VIN-15

> **Trạng thái:** Đề xuất, chưa triển khai · **Ngày:** 2026-11-15
> **Tài liệu liên quan:** [BRIEF.md](BRIEF.md) · [PRD.md](PRD.md) (v0.7) · [problem-statement.md](problem-statement.md)
> **Phạm vi tài liệu:** chỉ phần **mới** so với BRIEF và PRD. Không lặp lại những gì hai tài liệu đó đã có: ba agent đã nêu ở mục "Next" của BRIEF (monitor chủ động có phát hiện lệch chuẩn đầu ra, copilot cho sinh viên, agent duyệt sơ bộ cho giảng viên); ràng buộc "AI không quyết định" (FR-3.4); kiểm chứng trích dẫn (FR-5.4); luật giám sát (FR-7.x); các hạng mục hoãn hoặc chưa làm (PRD §1.3, NFR-13, OQ-2, OQ-10). Chưa sửa BRIEF, PRD hay code.

## 1. Vì sao cần đề xuất này

BRIEF chỉ nêu tên ba agent, mỗi agent một dòng. PRD chưa có yêu cầu (FR) nào cho agent. Chưa có gì nói agent được dùng công cụ nào, ghi được gì, và được kiểm soát ra sao. Ngoài ba agent đó, đề bài còn hai ý mà BRIEF và PRD chưa đề cập:

| Đề bài yêu cầu | Hiện trạng |
|---|---|
| Phát hiện **thiếu điều kiện xét công nhận tín chỉ** | Ngoài phạm vi (BRIEF "Out") |
| Benchmark kỹ năng **ESCO / O*NET** | Chưa dùng |

Tài liệu này bổ sung hai ý đó và chi tiết hóa cách xây ba agent đã nêu.

## 2. Phân loại công cụ và quy tắc ghi

| Loại | Ví dụ | Quy tắc |
|---|---|---|
| **Đọc** | `read_my_milestones`, `read_logs`, `get_outcomes`, `search_policy` | Tự chạy, trong phạm vi quyền của người đang đăng nhập (FR-1.3, FR-1.4) |
| **Soạn nháp** | `draft_log`, `draft_extension`, `draft_nudge` | Chỉ tạo bản nháp, không gửi; người dùng xác nhận mới có hiệu lực |
| **Cảnh báo** | `raise_flag` | Tạo `RiskFlag` như monitor hiện tại, không đổi trạng thái hồ sơ (FR-7.6) |
| **Quyết định** | duyệt, từ chối, công nhận tín chỉ | **Không cấp cho agent** |

**Ghi vết riêng cho agent:** mỗi lượt agent ghi một `audit_event` với `actor_kind = agent`, gồm công cụ đã gọi và dữ liệu đã đọc. Hiện `audit_event` đã có trường `actor_kind` nên không cần đổi lược đồ.

## 3. Bốn agent: chi tiết bổ sung

### 3.1. Monitor chủ động (nâng cấp monitor) — ưu tiên 1

**Hành vi:**
- Chạy **sau** các luật cứng hiện có (FR-7.2), không thay thế chúng.
- Đọc nhật ký tuần, đề cương và minh chứng của sinh viên, so với danh sách chuẩn đầu ra của chương trình.
- Phát hiện: công việc không liên quan chuẩn đầu ra, nhật ký lặp lại nội dung, khó khăn xuất hiện nhiều tuần liền, dấu hiệu bỏ dở.
- Có thể ánh xạ công việc sang kỹ năng ESCO / O*NET để giải thích *lệch ở chỗ nào*, thay vì chỉ nói "lệch".
- Tự chọn hồ sơ cần xem sâu hơn thay vì quét đều tất cả.

**Công cụ:** `read_logs`, `read_milestones`, `read_outline`, `get_outcomes`, `search_policy`, `raise_flag`, `draft_nudge`.

**Đầu ra:** cảnh báo loại mới (`outcome_drift`, `stalled_progress`) kèm lý do và đoạn nhật ký làm bằng chứng, cộng một bản nháp tin nhắc việc cho sinh viên.

**Người quyết:** giảng viên xác nhận trước khi gửi tin nhắc việc hoặc leo thang. Cảnh báo dùng lại cơ chế xác nhận, giải quyết hoặc bác bỏ có ghi chú của FR-7.7.

**Rủi ro:** cảnh báo sai làm giảng viên mất tin (MET-6 ≤ 15% bị bác bỏ). Cần bộ đánh giá (mục 4) trước khi bật mặc định.

### 3.2. Copilot cho sinh viên — ưu tiên 2

**Hành vi:**
- Trả lời dựa trên hồ sơ thật của chính sinh viên: còn mốc nào, hạn khi nào, thiếu minh chứng gì, giờ thực tập đang ở đâu so với yêu cầu.
- Soạn nháp nhật ký tuần từ ghi chú rời rạc.
- Soạn nháp đơn xin gia hạn kèm điều khoản liên quan, đúng giới hạn 14 ngày (FR-8.1).
- Kiểm tra hồ sơ trước khi nộp và giải thích lỗi bằng ngôn ngữ dễ hiểu.

**Công cụ:** `read_my_*` (chỉ dữ liệu của chính người hỏi), `search_policy`, `draft_log`, `draft_extension`.

**Người quyết:** sinh viên xem và bấm gửi.

**Bảo mật:** cho agent đọc hồ sơ cá nhân làm tăng lượng dữ liệu đi qua mô hình, nên cần trường đồng ý (mở rộng OQ-2). Che PII (NFR-7) vẫn áp dụng.

### 3.3. Agent duyệt sơ bộ cho giảng viên — ưu tiên 3

**Hành vi:** với mỗi mục trong hàng đợi, agent:
1. Chạy kiểm tra quy chế (FR-2.4).
2. Tra các điều khoản liên quan.
3. Kiểm tra độ lệch chuẩn đầu ra (dùng lại 3.1).
4. Xem lịch sử các lần duyệt, gia hạn, cảnh báo trước đó.
5. **Xếp ưu tiên cả hàng đợi** và viết khuyến nghị có trích dẫn.

**Công cụ:** chỉ đọc, cộng `draft_review_note`.

**Người quyết:** giảng viên. Khuyến nghị gắn nhãn "Gợi ý của AI"; lý do duyệt hoặc từ chối vẫn do giảng viên viết (FR-3.5).

### 3.4. Agent kiểm tra điều kiện công nhận tín chỉ (chỉ tư vấn) — ưu tiên 4

**Hành vi:** lập checklist điều kiện theo quy chế (đủ tuần, đủ giờ, đủ minh chứng, đã có đánh giá) và báo còn thiếu gì, còn bao lâu. **Không ra quyết định công nhận**; chỉ trả lời "đủ điều kiện để đưa ra xét" hay "còn thiếu".

**Lưu ý:** BRIEF đang để công nhận tín chỉ ở mục "Out". Agent này chỉ tư vấn nên không vi phạm nguyên tắc quyết định, nhưng phải chốt lại phạm vi trước khi đưa vào. Làm sau cùng, và chỉ khi quy chế công nhận tín chỉ đã được nạp vào kho quy chế.

## 4. Hạ tầng đề xuất làm kèm

| Hạng mục | Lý do | Hiện trạng |
|---|---|---|
| **Bộ đánh giá chất lượng (R16)** | Với dự án AI cần số liệu: tỷ lệ bắt đúng lệch chuẩn, tỷ lệ cảnh báo bị bác bỏ. Đề xuất đưa khỏi danh sách hoãn. | Hoãn (PRD §1.3, OQ-4) |
| **Truy vết từng lượt agent và chi phí** | Gỡ lỗi, kiểm soát chi phí, trình bày. | NFR-13 "Not built" |
| **Giới hạn bước, thời gian, chi phí mỗi lượt** | Agent gọi nhiều công cụ nên chậm và tốn hơn; cần trần số bước và ngân sách thời gian như FR-5.11. | Mới có cho trợ lý (FR-5.11) |

**Tái dùng template:** `CLAUDE.md` mô tả `src/agents/graph.py` là vòng lặp ReAct có ngắt HITL cho công cụ rủi ro. Có thể dùng làm nền cho các agent trên thay vì viết mới. **Chưa kiểm tra** xem mã đó có khớp nhu cầu không; cần đọc `src/agents/graph.py` trước khi chốt thiết kế.

## 5. Thứ tự đề xuất

| Bước | Nội dung | Phụ thuộc |
|---|---|---|
| 1 | Bộ công cụ đọc dùng chung (nhật ký, mốc, chuẩn đầu ra, quy chế) theo phạm vi quyền | Không |
| 2 | Bộ đánh giá nhỏ + truy vết lượt agent | Bước 1 |
| 3 | Monitor chủ động (3.1) | Bước 1, 2 |
| 4 | Agent duyệt sơ bộ (3.3), dùng lại phân tích lệch của 3.1 | Bước 3 |
| 5 | Copilot sinh viên (3.2) | Bước 1, 2 |
| 6 | Agent điều kiện tín chỉ (3.4), nếu còn thời gian | Quy chế tín chỉ đã nạp |

Ba agent đầu dùng chung bộ công cụ đọc ở bước 1, nên chi phí tăng thêm cho mỗi agent sau không lớn.

## 6. Câu hỏi cần chốt

| ID | Câu hỏi | Ghi chú |
|---|---|---|
| Q-1 | Dùng mô hình nào cho agent? | PRD §12.1: Qwen2.5 1.5B trên CPU mất 10–16 giây cho một câu trả lời đơn, vượt ngân sách 8 giây. Agent gọi nhiều lượt nên cần API hosted hoặc GPU (OQ-10). |
| Q-2 | Trường có đồng ý cho nhật ký và hồ sơ cá nhân đã che PII đi qua mô hình hosted không? | Mở rộng OQ-2: agent 3.1 và 3.2 đọc nhiều dữ liệu cá nhân hơn trợ lý hiện tại. |
| Q-3 | Chuẩn đầu ra lấy từ đâu và theo cấp nào (chương trình, học phần)? | Hiện là từ khóa trong `cohort.yaml`; liên quan OQ-8. |
| Q-4 | Có dùng ESCO / O*NET thật hay chỉ một bảng ánh xạ nhỏ do team tự lập? | Đề bài gợi ý dùng; chưa rõ phạm vi cần thiết. |
| Q-5 | Tin nhắc việc do agent soạn có cần giảng viên duyệt từng tin, hay duyệt theo lô? | Ảnh hưởng đến khối lượng việc của giảng viên. |

## 7. Cần cập nhật nếu chấp nhận đề xuất

Chưa làm; liệt kê để theo dõi.

- **BRIEF.md:** mục "Next" đã nêu ba agent nên không phải viết lại. Chỉ cần: chuyển các agent từ "Next" sang trạng thái đang làm khi bắt đầu triển khai; nếu nhận agent 3.4 thì sửa mục "Out" và "Scope".
- **PRD.md:**
  - §1.3: bỏ "AI scoring of learning-outcome drift" khỏi danh sách hoãn.
  - §3 Goals: thêm mục tiêu về agent.
  - §5: thêm mục FR mới cho từng agent (ID, tiêu chí chấp nhận, trạng thái "Not built").
  - §8: NFR-13 (truy vết) và ngân sách thời gian cho agent.
  - §10: thêm chỉ số cho độ chính xác phát hiện lệch.
  - §11: kế hoạch kiểm thử và bộ đánh giá.
  - §14: OQ liên quan Q-1 đến Q-5.
  - §15: thêm dòng vào change log.
- **docs/wireframe/:** thêm khung cho copilot, hộp "Gợi ý của AI" mở rộng ở hàng đợi và loại cảnh báo mới.
- **docs/architecture_diagram.md:** thêm tầng agent và bộ công cụ.

## 8. Chưa kiểm tra

- Chưa đọc `src/agents/graph.py` và các node hiện có, nên chưa rõ mức tái dùng được.
- Chưa đo chất lượng phát hiện lệch chuẩn đầu ra của bất kỳ mô hình nào; mọi ước lượng độ chính xác ở trên là mục tiêu, chưa phải kết quả.
- Chưa đánh giá chi phí và độ trễ thực tế của agent nhiều lượt trên hạ tầng của trường.
