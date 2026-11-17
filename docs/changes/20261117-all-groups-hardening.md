# Hardening checklist — cả 3 nhóm

## Đã hoàn thành bằng code/test

- Nhóm 1: sửa chuẩn hóa OCR nhầm `O/0` và `l/1` cho ngày tháng, số điện thoại;
  thêm test hồi quy.
- Nhóm 2: gom đồng hồ nghiệp vụ theo `Asia/Ho_Chi_Minh` (có cấu hình timezone),
  dùng cho monitor scheduler, monitor event và summary/export; thêm test.
- Nhóm 1: đặt ngân sách thời gian cho tóm tắt đề cương bằng
  `REVIEWER_SUMMARY_BUDGET_SECONDS`.
- Kiểm tra upload magic bytes/kích thước và URL ký đã có sẵn trong backend; các
  test API hiện hành tiếp tục chạy qua.

## Chưa thể xác minh tự động trong môi trường này

- OCR trên 20 bản scan thật và chạy model thật cần dữ liệu/credential bên ngoài.
- Test UI React cần bộ hướng dẫn frontend và browser runner; hai file
  `docs/FRONTEND_ARCHITECTURE.md`, `docs/UI_DESIGN.md` không tồn tại trên `main`.
