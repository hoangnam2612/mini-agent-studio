"""Che PII trước khi gửi bất cứ thứ gì tới LLM (R15.2, P6).

Hai lớp: (1) thay các giá trị đã biết của người hỏi bằng placeholder,
(2) regex cho email, SĐT VN, mã số thuế/CCCD, MSSV. Ánh xạ placeholder
chỉ nằm trong object Redactor của request, không lưu.
"""

from __future__ import annotations

import re

_PATTERNS = (
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")),
    ("SDT", re.compile(r"(?<!\d)(\+84|0)(\s?\d){9,10}(?!\d)")),
    ("SO_ID", re.compile(r"(?<!\d)\d{10}(-\d{3})?(?!\d)|(?<!\d)\d{12}(?!\d)")),
    ("MSSV", re.compile(r"\b[Ss][Vv]\d{4,}\b|(?<!\d)\d{8}(?!\d)")),
)


class Redactor:
    def __init__(self, known: dict[str, str | None] | None = None):
        # known: {"HO_TEN": "Nguyễn Văn A", "MSSV": "SV2026001", ...}
        self.known = {k: v for k, v in (known or {}).items() if v and len(v.strip()) >= 3}

    def redact(self, text: str) -> str:
        out = text
        # Giá trị dài thay trước để không cắt vụn tên đầy đủ
        for label, value in sorted(self.known.items(), key=lambda kv: -len(kv[1])):
            out = re.sub(re.escape(value), f"<{label}>", out, flags=re.I)
        for label, pattern in _PATTERNS:
            out = pattern.sub(f"<{label}>", out)
        return out

    def leaked(self, text: str) -> list[str]:
        """Giá trị PII đã biết còn sót trong text — dùng cho test/assert."""
        return [v for v in self.known.values() if v.lower() in text.lower()]
