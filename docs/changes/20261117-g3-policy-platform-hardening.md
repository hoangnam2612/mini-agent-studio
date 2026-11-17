# Nhóm 3 — hardening nền tảng policy assistant

## Thay đổi

- Grounding cho phép paraphrase tiếng Việt có kiểm soát, nhưng vẫn bắt buộc số liệu
  xuất hiện trong điều khoản nguồn.
- Rate limit hỗ trợ Redis sorted-set dùng chung giữa nhiều worker và tự fallback về
  bộ nhớ khi chạy local/test.
- Production từ chối JWT secret mặc định.
- OIDC kiểm chứng `id_token` RS256 bằng JWKS, issuer và audience trước khi tiếp tục.
- Bổ sung bộ eval policy 30 ca gồm câu hỏi đúng phạm vi, off-topic và adversarial.

## Kiểm chứng

- `pytest tests/ -q` (sau khi cài Pillow theo requirements): 188 passed, 1 skipped.
- `ruff check src tests` đạt.
- `python eval/run_eval.py --strict` chạy offline mặc định: 10/10 (100%).
