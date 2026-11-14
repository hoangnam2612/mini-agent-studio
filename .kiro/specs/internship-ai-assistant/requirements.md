# Requirements — VIN-15: Hệ thống hỗ trợ thực tập bằng AI

> Kiro spec · Giai đoạn 1/3 (Requirements → Design → Tasks) · **Phiên bản 2: thu hẹp phạm vi**
> Cú pháp tiêu chí nghiệm thu: **EARS** (`WHEN … THE SYSTEM SHALL …`, `IF … THEN …`, `WHERE …`).
> Số hiệu requirement giữ nguyên như phiên bản 1 để truy vết. Các requirement bị tạm gác được chuyển xuống mục 6 (Backlog).

## 1. Giới thiệu

Số sinh viên đi thực tập tăng nhanh khiến giảng viên quá tải vì hai việc: trả lời các câu hỏi lặp lại về thủ tục, và theo dõi thủ công hồ sơ, nhật ký thực tập.

Phiên bản này tập trung vào **vòng lõi giữa Sinh viên và Giảng viên**:

> SV khai báo hồ sơ (AI chuẩn hóa) → GV duyệt đề cương (HITL) → SV nộp nhật ký và minh chứng theo mốc → AI giám sát và nhắc việc → SV hỏi chính sách thì AI trả lời có trích dẫn → SV xin gia hạn thì GV duyệt (HITL, có lưu vết).

### 1.1 Ràng buộc cứng (từ đề bài)

| ID | Ràng buộc | Cách đáp ứng trong phạm vi hiện tại |
|----|-----------|---|
| C1 | **HITL bắt buộc** cho phê duyệt đề cương, xử lý ngoại lệ, công nhận tín chỉ | Phê duyệt đề cương (R3) và yêu cầu gia hạn mốc (R12) chỉ do GV quyết định. Công nhận tín chỉ tạm gác (Backlog), nhưng nguyên tắc "AI không có quyền quyết định" được enforce cho mọi cạnh quyết định. |
| C2 | **Trích dẫn đúng văn bản hiện hành** | R8, R9 |
| C3 | **Bảo mật** thông tin SV – DN | R1, R15 |

### 1.2 Phân tích bài toán

| Thành phần đề bài | Bản chất | Hệ quả thiết kế |
|---|---|---|
| Câu hỏi lặp lại về thủ tục | RAG có trích dẫn, cá nhân hóa theo ngữ cảnh SV | Kho quy định có ngày hiệu lực. Không có nguồn thì không trả lời. |
| Theo dõi hồ sơ, nhật ký | Workflow + state machine | Viết bằng code. Không dùng LLM cho logic trạng thái. |
| Chuẩn hóa hồ sơ | Trích xuất có cấu trúc | LLM structured output + validator. SV xác nhận trước khi lưu. |
| Phát hiện sớm rủi ro | Luật xác định | Phiên bản này **chỉ dùng luật** (trễ hạn, thiếu minh chứng, thiếu giờ). Phần đánh giá lệch CĐR bằng AI để vào Backlog. |

### 1.3 Ngoài phạm vi

- Ghép cặp SV – DN, ký số, hợp đồng ba bên.
- Thay thế hệ thống quản lý đào tạo; chấm điểm tự động.
- Mọi mục trong **Backlog** (mục 6).

## 2. Thuật ngữ

| Thuật ngữ | Định nghĩa |
|---|---|
| **SV** | Sinh viên / học viên đi thực tập |
| **GV** | Giảng viên hướng dẫn / phụ trách thực tập |
| **QTV** | Quản trị viên đào tạo (vai trò **tùy chọn**) |
| **Hồ sơ thực tập** | Một đợt thực tập của 1 SV tại 1 DN, gồm đăng ký, đề cương, mốc, nhật ký |
| **Mốc** | Hạn bắt buộc theo quy chế: nộp đăng ký, duyệt đề cương, nhật ký tuần, báo cáo giữa kỳ, báo cáo cuối kỳ |
| **Minh chứng** | File chứng minh hoàn thành mốc |
| **Yêu cầu gia hạn** | Ngoại lệ duy nhất trong phạm vi này: xin dời hạn một mốc |
| **Văn bản quy định** | Quy chế / hướng dẫn có số hiệu, ngày hiệu lực |
| **Cờ rủi ro** | Cảnh báo do Monitor sinh ra, có mức độ, lý do và bằng chứng |

## 3. Vai trò

| Vai trò | Loại | Chức năng |
|---|---|---|
| **Sinh viên (SV)** | Chính | Khai báo hồ sơ (AI hỗ trợ chuẩn hóa), nộp đề cương, nhật ký, minh chứng; xem timeline mốc; hỏi trợ lý AI; gửi yêu cầu gia hạn; nhận nhắc việc. |
| **Giảng viên (GV)** | Chính | Xem hàng chờ phê duyệt và SV có cờ rủi ro; 🔒 duyệt hồ sơ, đề cương, yêu cầu gia hạn; nhận xét nhật ký, minh chứng; xử lý cờ rủi ro; hỏi trợ lý AI. |
| **Quản trị viên (QTV)** | **Tùy chọn** | Cấu hình đợt và mẫu mốc; quản lý kho văn bản quy định; quản lý tài khoản và phân công GV. |

> **Khi không bật QTV:** cấu hình đợt, mẫu mốc và phân công GV được nạp từ file YAML/seed lúc khởi động. Quyền quản lý kho văn bản quy định chuyển cho GV có cờ `is_coordinator`.
>
> **Tác nhân hệ thống** (không phải vai trò người dùng): `AI-ASSIST` (trợ lý, trích xuất) và `AI-MONITOR` (giám sát theo luật). Cả hai **không bao giờ** được ra quyết định 🔒.

Chi tiết use case xem `use-cases.md`.

---

## 4. Yêu cầu chức năng

### Requirement 1 — Xác thực & phân quyền

**User story:** Là người dùng, tôi muốn đăng nhập và chỉ thấy dữ liệu mình được phép thấy.

1. THE SYSTEM SHALL xác thực người dùng và gán đúng 1 vai trò trong `student | lecturer | admin`. Vai trò `admin` chỉ có khi bật QTV.
2. THE SYSTEM SHALL hỗ trợ đăng nhập bằng tài khoản demo (JWT). WHERE có cấu hình OIDC THE SYSTEM SHALL dùng SSO/OIDC.
3. WHEN SV truy vấn dữ liệu THE SYSTEM SHALL chỉ trả về hồ sơ của chính SV đó.
4. WHEN GV truy vấn dữ liệu THE SYSTEM SHALL chỉ trả về hồ sơ của SV được phân công cho GV đó.
5. IF người dùng gọi API ngoài phạm vi quyền THEN THE SYSTEM SHALL trả 403 và ghi audit log.

### Requirement 2 — Khai báo & chuẩn hóa hồ sơ đăng ký

**User story:** Là SV, tôi muốn khai báo thông tin thực tập hoặc tải giấy tiếp nhận lên để hệ thống tự điền và chuẩn hóa, nhờ đó không bị trả hồ sơ vì sai định dạng.

1. THE SYSTEM SHALL cung cấp form gồm: DN (tên, mã số thuế, địa chỉ), người hướng dẫn DN (họ tên, email), vị trí, mô tả công việc, ngày bắt đầu/kết thúc, hình thức (toàn/bán thời gian).
2. WHEN SV tải lên giấy tiếp nhận (PDF/DOCX) THE SYSTEM SHALL trích xuất các trường trên và điền sẵn dưới dạng **gợi ý**, kèm độ tin cậy từng trường.
3. THE SYSTEM SHALL chuẩn hóa: định dạng ngày, email, SĐT, mã số thuế; khớp DN đã có theo mã số thuế.
4. WHEN lưu hồ sơ THE SYSTEM SHALL kiểm tra bằng luật xác định: đủ trường bắt buộc, thời lượng ≥ mức tối thiểu của quy chế, ngày nằm trong khung đợt.
5. IF một kiểm tra thất bại THEN THE SYSTEM SHALL báo lỗi cụ thể kèm trích dẫn điều khoản quy chế.
6. THE SYSTEM SHALL yêu cầu SV xác nhận dữ liệu do AI điền trước khi nộp. Các trường AI điền được đánh dấu riêng.
7. WHEN SV nộp THE SYSTEM SHALL chuyển `draft → submitted` và thông báo cho GV.

### Requirement 3 — Duyệt hồ sơ & đề cương (HITL)

**User story:** Là GV, tôi muốn duyệt hồ sơ và đề cương của SV nhanh, nhưng vẫn là người quyết định.

1. WHEN SV nộp hồ sơ hoặc đề cương THE SYSTEM SHALL đưa vào hàng chờ phê duyệt của GV phụ trách.
2. WHERE có LLM THE SYSTEM SHALL hiển thị bản tóm tắt đề cương và danh sách CĐR học phần mà đề cương **chưa nhắc tới**, gắn nhãn "Gợi ý của AI". Khi AI lỗi, GV vẫn duyệt bình thường.
3. THE SYSTEM SHALL chỉ cho vai trò GV chuyển trạng thái sang `approved | rejected | revision_requested`.
4. THE SYSTEM SHALL NOT cho phép tác tử AI hay tiến trình tự động ghi trạng thái quyết định.
5. WHEN GV ra quyết định `rejected` hoặc `revision_requested` THE SYSTEM SHALL bắt buộc nhập lý do. Mọi quyết định đều ghi audit log (người, thời điểm, quyết định, lý do, phiên bản).

### Requirement 4 — Mốc bắt buộc & theo dõi trạng thái

**User story:** Là SV, tôi muốn thấy rõ các mốc và trạng thái từng mốc để không bị trễ hạn.

1. THE SYSTEM SHALL lấy mẫu mốc của đợt từ cấu hình (QTV nhập trên UI, hoặc file YAML nếu không bật QTV). Mỗi mốc gồm: tên, hạn (tuyệt đối hoặc tương đối), loại minh chứng yêu cầu, căn cứ quy chế.
2. WHEN hồ sơ được duyệt THE SYSTEM SHALL sinh danh sách mốc cụ thể cho SV.
3. THE SYSTEM SHALL quản lý trạng thái mốc: `pending → submitted → accepted | rejected`. Mốc chưa nộp mà quá hạn chuyển `overdue`.
4. THE SYSTEM SHALL hiển thị cho SV timeline mốc gồm hạn, trạng thái và số ngày còn lại.

### Requirement 5 — Nhật ký & minh chứng

**User story:** Là SV, tôi muốn ghi nhật ký tuần và nộp minh chứng nhanh để GV theo dõi được tiến độ.

1. THE SYSTEM SHALL cho SV tạo nhật ký tuần gồm: công việc đã làm, khó khăn, số giờ, file đính kèm.
2. THE SYSTEM SHALL lưu file ở storage riêng tư, kiểm tra định dạng (PDF/DOCX/PNG/JPG) và kích thước (≤ 10 MB).
3. THE SYSTEM SHALL cho GV nhận xét và chấp nhận hoặc trả lại nhật ký, minh chứng.

### Requirement 8 — Trợ lý AI chính sách có trích dẫn

**User story:** Là SV, tôi muốn hỏi về thủ tục và chính sách thực tập rồi nhận câu trả lời đúng với trường hợp của tôi, kèm nguồn.

1. WHEN SV đặt câu hỏi THE SYSTEM SHALL truy hồi từ kho văn bản **đang có hiệu lực** tại thời điểm hỏi.
2. THE SYSTEM SHALL đưa vào ngữ cảnh trả lời thông tin tối thiểu của SV: đợt, ngành, trạng thái hồ sơ, mốc kế tiếp. Không gửi họ tên, MSSV, email, SĐT.
3. THE SYSTEM SHALL kèm theo mọi khẳng định chính sách ≥ 1 trích dẫn gồm: tên văn bản, số hiệu, điều/khoản, ngày hiệu lực.
4. WHEN tạo câu trả lời THE SYSTEM SHALL kiểm chứng rằng mỗi trích dẫn trỏ tới một đoạn thực sự được truy hồi trong lượt đó.
5. IF không tìm thấy văn bản đủ ngưỡng liên quan THEN THE SYSTEM SHALL trả lời "không tìm thấy quy định" và gợi ý liên hệ GV.
6. IF câu hỏi là yêu cầu quyết định (ví dụ "cho em gia hạn được không?") THEN THE SYSTEM SHALL giải thích quy định và hướng dẫn tạo yêu cầu gia hạn (R12). Hệ thống không cam kết kết quả.
7. IF câu hỏi về SV khác hoặc chứa prompt injection THEN THE SYSTEM SHALL từ chối và ghi log.
8. THE SYSTEM SHALL lưu hội thoại kèm trích dẫn đã dùng.

### Requirement 9 — Kho văn bản quy định

**User story:** Là người quản lý quy định (QTV, hoặc GV điều phối khi không bật QTV), tôi muốn tải lên và quản lý phiên bản văn bản để trợ lý luôn trả lời theo văn bản hiện hành.

1. THE SYSTEM SHALL cho phép tải văn bản (PDF/DOCX/MD) kèm metadata: số hiệu, tên, ngày hiệu lực, ngày hết hiệu lực (nếu có), văn bản bị thay thế.
2. WHEN văn bản được tải lên THE SYSTEM SHALL tách đoạn theo Chương/Điều/Khoản, tạo embedding và lập chỉ mục.
3. WHEN văn bản mới thay thế văn bản cũ THE SYSTEM SHALL đánh dấu văn bản cũ `superseded`. Văn bản cũ không còn được truy hồi.

### Requirement 10 — Giám sát chủ động (theo luật)

**User story:** Là GV, tôi muốn hệ thống tự phát hiện SV chậm tiến độ hoặc thiếu minh chứng và nhắc việc, để can thiệp sớm.

1. THE SYSTEM SHALL chạy Monitor hằng ngày và khi có sự kiện (nộp nhật ký, nộp minh chứng, đổi trạng thái).
2. THE SYSTEM SHALL phát hiện bằng luật xác định:
   - (a) mốc sắp đến hạn trong 3 ngày mà chưa nộp;
   - (b) mốc quá hạn;
   - (c) mốc đã nộp nhưng thiếu loại minh chứng yêu cầu;
   - (d) tổng giờ nhật ký lũy kế thấp hơn tiến độ kỳ vọng.
3. WHEN phát hiện rủi ro THE SYSTEM SHALL tạo cờ gồm: loại, mức (`info | warning | critical`), lý do, link bằng chứng.
4. THE SYSTEM SHALL NOT tạo trùng cờ cho cùng (hồ sơ, loại, mốc) khi cờ đó còn mở.
5. WHEN tạo cờ THE SYSTEM SHALL gửi thông báo in-app cho SV, và cho GV nếu mức ≥ `warning`.
6. THE SYSTEM SHALL NOT tự động thay đổi trạng thái hồ sơ dựa trên cờ.
7. THE SYSTEM SHALL cho GV xử lý cờ: `acknowledge | resolve | dismiss` (dismiss phải kèm lý do).

### Requirement 12 — Yêu cầu gia hạn mốc (HITL, có lưu vết)

**User story:** Là SV, tôi muốn xin gia hạn một mốc và theo dõi kết quả minh bạch.

1. THE SYSTEM SHALL cho SV tạo yêu cầu gia hạn cho 1 mốc chưa `accepted`, gồm: hạn mới đề xuất, lý do, file minh chứng (tùy chọn).
2. WHERE có LLM THE SYSTEM SHALL hiển thị cho GV bản tóm tắt yêu cầu và điều khoản quy chế liên quan, gắn nhãn "Gợi ý của AI".
3. THE SYSTEM SHALL chỉ cho GV phụ trách quyết định `approved | rejected` (một bước duyệt) và bắt buộc nhập lý do.
4. WHEN yêu cầu được duyệt THE SYSTEM SHALL dời `due_at` của mốc trong cùng transaction, liên kết thay đổi với yêu cầu, và gỡ trạng thái `overdue` nếu có.
5. THE SYSTEM SHALL ghi audit trail append-only cho mọi hành động trên yêu cầu (tạo, hủy, duyệt, từ chối), gồm người, thời điểm, giá trị trước/sau.

### Requirement 15 — Bảo mật & quyền riêng tư (cốt lõi)

1. THE SYSTEM SHALL dùng HTTPS khi triển khai và không cho truy cập công khai file. File chỉ tải được qua URL có hạn.
2. WHEN gửi dữ liệu tới LLM THE SYSTEM SHALL che PII: họ tên, MSSV, email, SĐT, mã số thuế.
3. THE SYSTEM SHALL ghi audit log mọi thay đổi trạng thái và mọi lần truy cập bị từ chối.
4. THE SYSTEM SHALL không ghi PII vào log ứng dụng.

## 5. Yêu cầu phi chức năng

| ID | Yêu cầu |
|---|---|
| NFR-1 | Trợ lý AI: p95 ≤ 10 s; có streaming. |
| NFR-2 | Chạy bằng `docker compose up` với cấu hình qua `.env`. Có chế độ **mock LLM** khi không có API key. |
| NFR-3 | Giao diện tiếng Việt, dùng được trên mobile cho SV. |
| NFR-4 | Mọi prompt nằm trong `prompts/*.md`. |
| NFR-5 | Có test tự động cho state machine, phân quyền, kiểm chứng trích dẫn và luật Monitor. |

## 6. Backlog — tạm gác

| Req | Nội dung | Lý do gác / ghi chú |
|---|---|---|
| **R6** | Đánh giá từ doanh nghiệp (link token cho người hướng dẫn DN) | Theo yêu cầu. Tạm thời SV có thể nộp phiếu đánh giá đã ký như một minh chứng mốc (R4/R5). |
| ~~R7~~ | Danh sách tổng hợp có lọc/xuất CSV | **Đã đưa lại vào phạm vi và build ngày 2026-11-14** vì là đầu ra Cơ bản của đề bài — xem PRD FR-9.4 (`/internships-summary`). Tiêu chí nghiệm thu theo R7.1–R7.3 của spec phiên bản 1. |
| **R16** | Golden dataset & eval chất lượng AI | Theo yêu cầu. Vẫn giữ unit test cho bước kiểm chứng trích dẫn (NFR-5). |
| R11 | Tiền kiểm & công nhận tín chỉ | Thu hẹp phạm vi. Nguyên tắc HITL vẫn áp dụng khi làm sau. |
| R12 (mở rộng) | Nhiều loại ngoại lệ, chuỗi duyệt nhiều cấp | Thu hẹp thành 1 loại (gia hạn mốc), 1 bước duyệt. |
| R10.3 | Đánh giá lệch chuẩn đầu ra bằng AI (ESCO/O*NET) | Thu hẹp thành Monitor chỉ dùng luật. |
| R13 | Đồng bộ LMS | Thu hẹp phạm vi. |
| R14 | Dashboard BI | Thu hẹp phạm vi. |
| R15 (mở rộng) | Mã hóa cột PII, chính sách lưu trữ, k-anonymity | Thu hẹp thành bảo mật cốt lõi. |
| — | Vai trò Lãnh đạo Khoa, Quản trị hệ thống, Người hướng dẫn DN | Gộp vào QTV tùy chọn hoặc gác lại. |

## 7. Giả định

- A1. Dữ liệu demo là dữ liệu tổng hợp (synthetic): khoảng 30 SV, 3 GV, 1 đợt, 3–4 văn bản quy chế mẫu.
- A2. Đã có bộ quy chế thực tập dạng số (PDF/DOCX) và danh sách CĐR học phần dạng văn bản.

## 8. Câu hỏi mở

1. Thiếu R7 có bị trừ điểm đầu ra "Cơ bản" không? Nếu có, cần đưa một danh sách tối thiểu (không lọc, không xuất) trở lại phạm vi.
2. Vai trò tùy chọn nên là QTV (như spec này) hay Người hướng dẫn DN?
3. Có được dùng LLM cloud với dữ liệu đã che PII không?
