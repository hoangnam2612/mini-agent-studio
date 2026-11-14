# Đề bài: Hệ thống hỗ trợ thực tập bằng AI

> Tài liệu cố định (nguồn yêu cầu gốc). Không đặt theo ngày; tài liệu theo từng thay đổi nằm ở `docs/changes/`.

## Mô tả bài toán

**Thực trạng:** Khi quy mô sinh viên đi thực tập doanh nghiệp tăng cao, giảng viên phụ trách và bộ phận quản lý đào tạo bị quá tải bởi hàng loạt câu hỏi lặp lại về thủ tục, điều kiện công nhận tín chỉ và việc theo dõi thủ công hồ sơ, nhật ký thực tập, đánh giá từ doanh nghiệp tiếp nhận.

**Vấn đề:** Làm thế nào để xây dựng nền tảng quản lý và đồng hành thực tập thông minh tích hợp AI Agent: tự động chuẩn hóa hồ sơ đăng ký thực tập, hướng dẫn quy trình – chính sách theo đúng ngữ cảnh cá nhân của từng sinh viên, đồng thời giám sát tiến độ theo các mốc bắt buộc để phát hiện sớm rủi ro trễ hạn, lệch chuẩn đầu ra hoặc thiếu điều kiện xét công nhận tín chỉ.

**Ràng buộc:** Mọi quyết định phê duyệt đề cương thực tập, xử lý ngoại lệ hoặc công nhận quy đổi tín chỉ bắt buộc có giảng viên/quản trị viên phê duyệt (HITL); câu trả lời chính sách phải trích dẫn đúng văn bản quy định hiện hành và bảo mật thông tin sinh viên – doanh nghiệp.

## Techstack gợi ý

- Next.js/React, FastAPI, PostgreSQL, lưu trữ hồ sơ/tài liệu, tích hợp LMS hoặc biểu mẫu qua API
- RAG trên quy định và hướng dẫn thực tập
- LLM, workflow engine, SSO/OIDC, Docker và dashboard BI
- Dữ liệu & benchmark thực tế tham chiếu: khung kỹ năng nghề nghiệp ESCO / O*NET kết hợp bộ quy chế đào tạo, biểu mẫu thực tập và dữ liệu theo dõi tiến độ học tập mẫu

## Yêu cầu đầu ra gợi ý

**Cơ bản:**
- Cổng quản lý thực tập trực tuyến (≥2 vai trò: Sinh viên & Giảng viên/Quản trị) cho phép khai báo – chuẩn hóa hồ sơ thực tập, theo dõi trạng thái từng mốc và xem danh sách tổng hợp.
- Trợ lý AI giải đáp thủ tục, yêu cầu học phần và chính sách thực tập có trích dẫn nguồn.

**Nâng cao:**
- Tác tử giám sát chủ động (Proactive Milestone & Compliance Monitor) tự động phát hiện hồ sơ thiếu minh chứng, chậm tiến độ hoặc nội dung công việc thực tập lệch chuẩn đầu ra để nhắc việc và cảnh báo.
- Luồng xử lý phê duyệt ngoại lệ có lưu vết, đồng bộ dữ liệu LMS và dashboard phân tích chất lượng thực tập toàn khóa.

## Phạm vi team chọn làm

> Team tự điền: yêu cầu nào làm trước, yêu cầu nào để sau.

- [ ] Cơ bản: cổng quản lý thực tập (Sinh viên & Giảng viên/Quản trị)
- [ ] Cơ bản: trợ lý AI giải đáp chính sách có trích dẫn nguồn
- [ ] Nâng cao: tác tử giám sát mốc & tuân thủ
- [ ] Nâng cao: phê duyệt ngoại lệ có lưu vết, đồng bộ LMS, dashboard
