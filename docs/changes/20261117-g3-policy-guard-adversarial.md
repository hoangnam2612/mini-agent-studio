# Nhóm 3 — tăng cường kiểm thử policy guard

## Thay đổi

- Chuẩn hoá Unicode, ký tự zero-width và khoảng trắng trước khi chạy guard.
- Bổ sung regression tests cho prompt injection bị ngắt dòng/che bằng zero-width,
  giả mạo vai trò quản trị, truy cập dữ liệu sinh viên khác và yêu cầu ra quyết định.

## Kiểm chứng

`pytest tests/test_vin15/test_policy_guard_adversarial.py -q`
