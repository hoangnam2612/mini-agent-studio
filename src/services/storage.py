"""Lưu file minh chứng ở thư mục riêng tư (R5.2, R15.1).

Kiểm tra cả đuôi file lẫn magic bytes — không tin Content-Type client gửi.
Tên file trên đĩa là sha256 + đuôi, không dùng tên người dùng đặt.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from src.config import get_settings

ALLOWED = {
    ".pdf": ("application/pdf", (b"%PDF",)),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", (b"PK\x03\x04",)),
    ".png": ("image/png", (b"\x89PNG",)),
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
}


class FileRejected(Exception):  # noqa: N818 — tên theo nghĩa nghiệp vụ, như GuardrailViolation
    pass


@dataclass
class StoredFile:
    filename: str
    path: str
    mime: str
    size: int
    sha256: str


def check_file(filename: str, content: bytes, allowed: dict = ALLOWED) -> str:
    """Trả MIME nếu hợp lệ; raise FileRejected nếu sai định dạng/kích thước."""
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    if not content:
        raise FileRejected("File rỗng")
    if len(content) > max_bytes:
        raise FileRejected(f"File vượt quá {get_settings().max_upload_mb} MB")
    ext = Path(filename).suffix.lower()
    if ext not in allowed:
        raise FileRejected(f"Định dạng {ext or '(không có đuôi)'} không được hỗ trợ — chỉ nhận {', '.join(allowed)}")
    mime, magics = allowed[ext]
    if not any(content.startswith(m) for m in magics):
        raise FileRejected("Nội dung file không khớp định dạng khai báo")
    return mime


def save_file(filename: str, content: bytes) -> StoredFile:
    mime = check_file(filename, content)
    digest = hashlib.sha256(content).hexdigest()
    folder = Path(get_settings().upload_dir)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{digest}{Path(filename).suffix.lower()}"
    if not target.exists():
        target.write_bytes(content)
    return StoredFile(Path(filename).name[:200], str(target), mime, len(content), digest)
