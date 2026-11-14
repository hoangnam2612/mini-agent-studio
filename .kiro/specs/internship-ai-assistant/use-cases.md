# Use Cases — VIN-15: Hệ thống hỗ trợ thực tập bằng AI

> Phiên bản 2: thu hẹp phạm vi. Bổ sung cho `requirements.md`.
> Ký hiệu: `UC-xx` = use case · `R<n>` = requirement · 🔒 **HITL** = chỉ con người được quyết định.
> Quy ước sơ đồ Mermaid `flowchart`:
> - Hình chữ nhật: tác nhân.
> - Hình bo tròn `([...])`: use case.
> - Mũi tên nét đứt: quan hệ `«include»` / `«extend»`.

---

## 1. Vai trò

### 1.1 Danh sách tác nhân

| Tác nhân | Loại | Xác thực | Phạm vi dữ liệu |
|---|---|---|---|
| **Sinh viên (SV)** | Người — **chính** | JWT demo / OIDC | Chỉ hồ sơ của bản thân |
| **Giảng viên (GV)** | Người — **chính** | JWT demo / OIDC | SV được phân công |
| **Quản trị viên (QTV)** | Người — **tùy chọn** | JWT demo / OIDC | Cấu hình, kho quy định, tài khoản. Không cần xem nội dung nhật ký SV. |
| Trợ lý AI (`AI-ASSIST`) | Hệ thống | Service | Văn bản quy định + ngữ cảnh SV đã che PII |
| Tác tử giám sát (`AI-MONITOR`) | Hệ thống | Service | Đọc mốc, nhật ký. Chỉ ghi cờ rủi ro và thông báo. |
| Bộ lập lịch (`SCHEDULER`) | Hệ thống | — | Kích hoạt job hằng ngày |
| LLM Provider | Ngoài | API key | — |

> **Khi không bật QTV:** đợt, mẫu mốc, tài khoản và phân công GV được nạp từ file YAML/seed. UC-51 (kho quy định) chuyển cho GV có cờ `is_coordinator`.

### 1.2 Chức năng từng vai trò

**① Sinh viên**
- Khai báo hồ sơ đăng ký; tải giấy tiếp nhận để AI trích xuất và chuẩn hóa; xác nhận rồi nộp.
- Nộp và sửa đề cương.
- Xem timeline mốc; nộp minh chứng; ghi nhật ký tuần.
- Hỏi trợ lý AI chính sách, nhận câu trả lời có trích dẫn.
- Gửi yêu cầu gia hạn mốc và theo dõi kết quả.
- Nhận nhắc việc, cảnh báo.

**② Giảng viên**
- Xem hàng chờ phê duyệt và danh sách SV có cờ rủi ro.
- 🔒 Duyệt hồ sơ đăng ký và đề cương, có tham khảo gợi ý AI về CĐR chưa được nhắc tới.
- Nhận xét, chấp nhận hoặc trả lại nhật ký và minh chứng.
- 🔒 Duyệt hoặc từ chối yêu cầu gia hạn mốc.
- Xử lý cờ rủi ro; xem lịch sử (audit) hồ sơ của SV mình.
- Hỏi trợ lý AI chính sách.

**③ Quản trị viên (tùy chọn)**
- Cấu hình đợt thực tập và mẫu mốc.
- Quản lý kho văn bản quy định (tải lên, hiệu lực, thay thế).
- Quản lý tài khoản và phân công GV cho SV.

### 1.3 Ma trận phân quyền

✅ thực hiện · 👁 xem · 🔒 quyết định HITL · ✏️ chỉ gợi ý/tạo cờ · — không có quyền

| Chức năng | SV | GV | QTV *(opt)* | AI-ASSIST | AI-MONITOR |
|---|---|---|---|---|---|
| Khai báo / nộp hồ sơ | ✅ (của mình) | 👁 | 👁 | ✏️ trích xuất | — |
| Duyệt hồ sơ / đề cương | — | 🔒 | — | ✏️ tóm tắt, CĐR chưa nhắc tới | — |
| Nhật ký / minh chứng | ✅ | 👁 + nhận xét | — | — | 👁 |
| Hỏi trợ lý AI | ✅ | ✅ | ✅ | ✅ trả lời | — |
| Gửi yêu cầu gia hạn | ✅ | — | — | — | — |
| Duyệt gia hạn | — | 🔒 | — | ✏️ tóm tắt + điều khoản | — |
| Cờ rủi ro | 👁 (của mình) | ✅ xử lý | — | — | ✏️ tạo |
| Cấu hình đợt / mốc | — | — | ✅ | — | — |
| Kho văn bản quy định | 👁 | 👁 (✅ nếu là điều phối và không bật QTV) | ✅ | 👁 truy hồi | — |
| Tài khoản / phân công | — | — | ✅ | — | — |
| Audit trail | — | 👁 (SV của mình) | 👁 | — | — |

> **Bất biến:** cột AI không bao giờ chứa 🔒. Bất biến này được enforce bằng `transition()` (`design.md` §3.1, thuộc tính P1).

---

## 2. Sơ đồ use case tổng quan

```mermaid
flowchart LR
  classDef actor fill:#dbeafe,stroke:#1d4ed8,color:#0f172a
  classDef optactor fill:#f1f5f9,stroke:#64748b,stroke-dasharray:4 3,color:#0f172a
  classDef sysactor fill:#fef3c7,stroke:#b45309,color:#0f172a
  classDef ext fill:#e5e7eb,stroke:#6b7280,color:#0f172a
  classDef hitl fill:#fee2e2,stroke:#b91c1c,color:#0f172a

  SV["👤 Sinh viên"]:::actor
  GV["👤 Giảng viên"]:::actor
  QTV["👤 Quản trị viên (tùy chọn)"]:::optactor

  subgraph SYS["Hệ thống hỗ trợ thực tập bằng AI"]
    direction TB
    P1(["Khai báo & chuẩn hóa hồ sơ"])
    P2(["Mốc, nhật ký & minh chứng"])
    P3(["Trợ lý AI chính sách có trích dẫn"])
    P4(["🔒 Phê duyệt: hồ sơ, đề cương, gia hạn"]):::hitl
    P5(["Giám sát & cảnh báo rủi ro"])
    P6(["Cấu hình đợt, mốc & kho quy định"])
  end

  AIA["🤖 Trợ lý AI"]:::sysactor
  AIM["🤖 Tác tử giám sát"]:::sysactor
  SCH["⏰ Bộ lập lịch"]:::sysactor
  LLM["LLM Provider"]:::ext

  SV --- P1 & P2 & P3 & P5
  GV --- P2 & P3 & P4 & P5
  QTV -.- P6

  P1 --- AIA
  P3 --- AIA
  P4 --- AIA
  P5 --- AIM
  SCH --- P5
  AIA --- LLM
```

---

## 3. Sơ đồ use case theo vai trò

### 3.1 Sinh viên

```mermaid
flowchart LR
  classDef actor fill:#dbeafe,stroke:#1d4ed8,color:#0f172a
  classDef sysactor fill:#fef3c7,stroke:#b45309,color:#0f172a

  SV["👤 Sinh viên"]:::actor

  subgraph SYS["Hệ thống hỗ trợ thực tập"]
    direction TB
    UC01(["UC-01 Đăng nhập"])
    UC10(["UC-10 Khai báo hồ sơ đăng ký"])
    UC11(["UC-11 Tải giấy tiếp nhận để AI trích xuất"])
    UC12(["UC-12 Xác nhận dữ liệu AI điền"])
    UC13(["UC-13 Nộp hồ sơ"])
    UC14(["UC-14 Kiểm tra điều kiện theo quy chế"])
    UC15(["UC-15 Nộp / sửa đề cương"])
    UC16(["UC-16 Xem timeline mốc"])
    UC17(["UC-17 Nộp minh chứng mốc"])
    UC18(["UC-18 Ghi nhật ký tuần"])
    UC20(["UC-20 Hỏi trợ lý AI chính sách"])
    UC21(["UC-21 Truy hồi quy định đang hiệu lực"])
    UC22(["UC-22 Kiểm chứng trích dẫn"])
    UC23(["UC-23 Gửi yêu cầu gia hạn mốc"])
    UC25(["UC-25 Theo dõi yêu cầu gia hạn"])
    UC28(["UC-28 Nhận nhắc việc & cảnh báo"])
  end

  AIA["🤖 Trợ lý AI"]:::sysactor

  SV --- UC01 & UC10 & UC13 & UC15 & UC16 & UC17 & UC18 & UC20 & UC23 & UC25 & UC28

  UC11 -.->|"«extend»"| UC10
  UC11 -.->|"«include»"| UC12
  UC13 -.->|"«include»"| UC14
  UC20 -.->|"«include»"| UC21
  UC20 -.->|"«include»"| UC22
  UC23 -.->|"«extend» được gợi ý từ chat"| UC20

  UC11 --- AIA
  UC21 --- AIA
```

### 3.2 Giảng viên

```mermaid
flowchart LR
  classDef actor fill:#dbeafe,stroke:#1d4ed8,color:#0f172a
  classDef sysactor fill:#fef3c7,stroke:#b45309,color:#0f172a
  classDef hitl fill:#fee2e2,stroke:#b91c1c,color:#0f172a

  GV["👤 Giảng viên"]:::actor

  subgraph SYS["Hệ thống hỗ trợ thực tập"]
    direction TB
    UC01(["UC-01 Đăng nhập"])
    UC30(["UC-30 Xem hàng chờ phê duyệt"])
    UC33(["🔒 UC-33 Duyệt hồ sơ đăng ký"]):::hitl
    UC31(["🔒 UC-31 Duyệt đề cương"]):::hitl
    UC32(["UC-32 Xem gợi ý AI: tóm tắt & CĐR chưa nhắc tới"])
    UC34(["UC-34 Nhận xét nhật ký & minh chứng"])
    UC37(["🔒 UC-37 Duyệt yêu cầu gia hạn"]):::hitl
    UC41(["UC-41 Xem tóm tắt yêu cầu & điều khoản do AI"])
    UC42(["UC-42 Ghi lý do quyết định"])
    UC35(["UC-35 Xem SV có cờ rủi ro"])
    UC36(["UC-36 Xử lý cờ rủi ro"])
    UC20(["UC-20 Hỏi trợ lý AI chính sách"])
    UC60(["UC-60 Xem lịch sử audit hồ sơ"])
  end

  AIA["🤖 Trợ lý AI"]:::sysactor

  GV --- UC01 & UC30 & UC33 & UC31 & UC34 & UC37 & UC35 & UC36 & UC20 & UC60

  UC31 -.->|"«include»"| UC32
  UC37 -.->|"«include»"| UC41
  UC31 -.->|"«include» khi từ chối / yêu cầu sửa"| UC42
  UC33 -.->|"«include» khi từ chối"| UC42
  UC37 -.->|"«include»"| UC42
  UC36 -.->|"«include» khi dismiss"| UC42

  UC32 --- AIA
  UC41 --- AIA
```

### 3.3 Quản trị viên (tùy chọn)

```mermaid
flowchart LR
  classDef optactor fill:#f1f5f9,stroke:#64748b,stroke-dasharray:4 3,color:#0f172a
  classDef sysactor fill:#fef3c7,stroke:#b45309,color:#0f172a

  QTV["👤 Quản trị viên (tùy chọn)"]:::optactor

  subgraph SYS["Hệ thống hỗ trợ thực tập"]
    direction TB
    UC50(["UC-50 Cấu hình đợt & mẫu mốc"])
    UC51(["UC-51 Quản lý kho văn bản quy định"])
    UC51a(["UC-51a Lập chỉ mục theo Điều/Khoản"])
    UC51b(["UC-51b Đánh dấu văn bản bị thay thế"])
    UC53(["UC-53 Quản lý tài khoản & phân công GV"])
  end

  AIA["🤖 Trợ lý AI"]:::sysactor

  QTV --- UC50 & UC51 & UC53
  UC51 -.->|"«include»"| UC51a
  UC51b -.->|"«extend» khi có văn bản thay thế"| UC51
  UC51a --- AIA
```

> Không bật QTV: UC-50 và UC-53 được thay bằng file `config/cohort.yaml` + `scripts/seed.py`; UC-51 do GV điều phối thực hiện.

### 3.4 Tác nhân hệ thống

```mermaid
flowchart LR
  classDef sysactor fill:#fef3c7,stroke:#b45309,color:#0f172a
  classDef actor fill:#dbeafe,stroke:#1d4ed8,color:#0f172a

  SCH["⏰ Bộ lập lịch"]:::sysactor
  AIM["🤖 Tác tử giám sát"]:::sysactor

  subgraph SYS["Hệ thống hỗ trợ thực tập"]
    direction TB
    UC100(["UC-100 Quét tiến độ hằng ngày / theo sự kiện"])
    UC101(["UC-101 Phát hiện mốc sắp hạn & quá hạn"])
    UC102(["UC-102 Phát hiện thiếu minh chứng & thiếu giờ"])
    UC104(["UC-104 Tạo cờ rủi ro không trùng lặp"])
    UC105(["UC-105 Thông báo SV & GV"])
    UC107(["UC-107 Chuyển mốc quá hạn sang overdue"])
  end

  SV["👤 Sinh viên"]:::actor
  GV["👤 Giảng viên"]:::actor

  SCH --- UC100 & UC107
  AIM --- UC100
  UC100 -.->|"«include»"| UC101
  UC100 -.->|"«include»"| UC102
  UC101 -.->|"«include»"| UC104
  UC102 -.->|"«include»"| UC104
  UC104 -.->|"«include»"| UC105
  UC105 --- SV & GV
```

> Phiên bản này, Monitor chạy **hoàn toàn bằng luật**, không gọi LLM. Phần đánh giá lệch CĐR bằng AI nằm trong Backlog.

---

## 4. Danh mục use case

| ID | Use case | Tác nhân chính | Req |
|---|---|---|---|
| UC-01 | Đăng nhập | SV, GV, QTV | R1 |
| UC-10 | Khai báo hồ sơ đăng ký | SV | R2.1 |
| UC-11 | Tải giấy tiếp nhận để AI trích xuất | SV (+AI-ASSIST) | R2.2–2.3 |
| UC-12 | Xác nhận dữ liệu AI điền | SV | R2.6 |
| UC-13 | Nộp hồ sơ | SV | R2.7 |
| UC-14 | Kiểm tra điều kiện theo quy chế | (hệ thống) | R2.4–2.5 |
| UC-15 | Nộp / sửa đề cương | SV | R3.1 |
| UC-16 | Xem timeline mốc | SV | R4.4 |
| UC-17 | Nộp minh chứng mốc | SV | R4.3, R5.2 |
| UC-18 | Ghi nhật ký tuần | SV | R5.1 |
| UC-20 | Hỏi trợ lý AI chính sách | SV, GV, QTV (+AI-ASSIST) | R8 |
| UC-21 | Truy hồi quy định đang hiệu lực | (hệ thống) | R8.1, R9.3 |
| UC-22 | Kiểm chứng trích dẫn | (hệ thống) | R8.3–8.4 |
| UC-23 | Gửi yêu cầu gia hạn mốc | SV | R12.1 |
| UC-25 | Theo dõi yêu cầu gia hạn | SV | R12 |
| UC-28 | Nhận nhắc việc & cảnh báo | SV, GV | R10.5 |
| UC-30 | Xem hàng chờ phê duyệt | GV | R3.1 |
| UC-31 | 🔒 Duyệt đề cương | GV | R3.3–3.5 |
| UC-32 | Xem gợi ý AI cho đề cương | GV (+AI-ASSIST) | R3.2 |
| UC-33 | 🔒 Duyệt hồ sơ đăng ký | GV | R3 |
| UC-34 | Nhận xét nhật ký & minh chứng | GV | R5.3 |
| UC-35 | Xem SV có cờ rủi ro | GV | R10 |
| UC-36 | Xử lý cờ rủi ro | GV | R10.7 |
| UC-37 | 🔒 Duyệt yêu cầu gia hạn | GV | R12.3–12.4 |
| UC-41 | Xem tóm tắt yêu cầu do AI | GV (+AI-ASSIST) | R12.2 |
| UC-42 | Ghi lý do quyết định | GV | R3.5, R12.3 |
| UC-50 | Cấu hình đợt & mẫu mốc | QTV *(opt)* | R4.1 |
| UC-51 | Quản lý kho văn bản quy định | QTV *(opt)* / GV điều phối | R9 |
| UC-53 | Quản lý tài khoản & phân công GV | QTV *(opt)* | R1.4 |
| UC-60 | Xem lịch sử audit hồ sơ | GV | R12.5, R15.3 |
| UC-100 | Quét tiến độ | AI-MONITOR, SCHEDULER | R10.1 |
| UC-101 | Phát hiện mốc sắp hạn & quá hạn | AI-MONITOR | R10.2a–b |
| UC-102 | Phát hiện thiếu minh chứng & thiếu giờ | AI-MONITOR | R10.2c–d |
| UC-104 | Tạo cờ rủi ro không trùng lặp | AI-MONITOR | R10.3–10.4 |
| UC-105 | Thông báo SV & GV | AI-MONITOR | R10.5 |
| UC-107 | Chuyển mốc quá hạn sang overdue | SCHEDULER | R4.3 |

---

## 5. Đặc tả use case trọng yếu

### UC-20 — Hỏi trợ lý AI chính sách

| Mục | Nội dung |
|---|---|
| Tác nhân | SV (chính); AI-ASSIST, LLM (phụ) |
| Tiền điều kiện | Đã đăng nhập; kho quy định có ≥ 1 văn bản `active` |
| Hậu điều kiện | Hội thoại và trích dẫn được lưu; không thay đổi trạng thái nghiệp vụ nào |
| Luồng chính | 1. SV nhập câu hỏi. 2. Guardrail kiểm tra (injection, hỏi về SV khác, ép quyết định). 3. Lấy ngữ cảnh SV đã che PII. 4. Truy hồi quy định đang hiệu lực (UC-21). 5. LLM soạn câu trả lời có marker trích dẫn. 6. Kiểm chứng trích dẫn (UC-22). 7. Trả lời kèm danh sách nguồn. |
| Luồng thay thế | **2a** Vi phạm guardrail → từ chối, ghi log. **4a** Không có đoạn đủ ngưỡng → "không tìm thấy quy định, hãy liên hệ GV". **5a** Câu hỏi cần quyết định → giải thích quy định và gợi ý UC-23. **6a** Trích dẫn sai → sinh lại 1 lần; vẫn sai thì bỏ các câu không có nguồn. |

### UC-31 — 🔒 Duyệt đề cương

| Mục | Nội dung |
|---|---|
| Tác nhân | GV |
| Tiền điều kiện | Đề cương ở trạng thái `submitted`; GV được phân công cho SV này |
| Hậu điều kiện | Đề cương ở trạng thái `approved` / `rejected` / `revision_requested`; có 1 audit event; SV được thông báo |
| Luồng chính | 1. GV mở hàng chờ. 2. Xem đề cương và gợi ý AI (UC-32). 3. Chọn quyết định, nhập lý do nếu cần (UC-42). 4. Hệ thống gọi `transition()` với `actor.kind = human`, ghi audit, thông báo SV. |
| Luồng thay thế | **2a** AI lỗi → vẫn hiển thị đề cương, không có gợi ý. **4a** Đề cương đã bị sửa trong lúc GV xem (khác `version`) → 409, yêu cầu tải lại. |

### UC-23 → UC-37 — Gia hạn mốc

```mermaid
sequenceDiagram
  actor SV as Sinh viên
  participant AI as 🤖 Trợ lý AI
  participant WF as Workflow Service
  actor GV as Giảng viên

  SV->>AI: "Em có được gia hạn nộp báo cáo giữa kỳ không?"
  AI-->>SV: Giải thích quy định + trích dẫn + nút "Tạo yêu cầu gia hạn"
  SV->>WF: Gửi yêu cầu (mốc, hạn mới, lý do, minh chứng)
  WF->>WF: Ghi audit "created"
  WF->>AI: Tóm tắt + điều khoản liên quan
  WF->>GV: Thông báo — chờ duyệt
  GV->>WF: 🔒 Duyệt / Từ chối + lý do
  alt Duyệt
    WF->>WF: Dời due_at, gỡ overdue, ghi audit (trong 1 transaction)
  else Từ chối
    WF->>WF: Ghi audit, mốc giữ nguyên
  end
  WF-->>SV: Thông báo kết quả
```

| Mục | Nội dung |
|---|---|
| Ràng buộc | AI chỉ gợi ý tạo yêu cầu; SV tự bấm gửi. Chỉ GV phụ trách mới duyệt được. |
| Luồng thay thế | SV hủy yêu cầu khi chưa có quyết định. Mốc đã `accepted` thì không được xin gia hạn. |

### UC-100 → UC-105 — Giám sát chủ động

| Mục | Nội dung |
|---|---|
| Kích hoạt | Hằng ngày 07:00, hoặc sự kiện nộp nhật ký / minh chứng / đổi trạng thái |
| Luồng chính | 1. Tải hồ sơ `in_progress`. 2. Chạy luật (a)–(d). 3. Upsert cờ (không trùng khi cờ cùng loại còn mở). 4. Thông báo SV; thông báo GV nếu mức ≥ `warning`. |
| Ràng buộc | Không thay đổi trạng thái hồ sơ. Không gọi LLM. |
