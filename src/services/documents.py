"""Đọc text từ PDF / DOCX / TXT / MD — dùng chung cho intake (R2.2) và kho quy định (R9)."""

from __future__ import annotations

import io
from pathlib import Path


class UnreadableDocument(Exception):  # noqa: N818
    pass


def extract_text(filename: str, content: bytes) -> str:
    ext = Path(filename).suffix.lower()
    try:
        if ext == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        if ext == ".docx":
            from docx import Document

            doc = Document(io.BytesIO(content))
            lines = [p.text for p in doc.paragraphs]
            for table in doc.tables:
                for row in table.rows:
                    lines.append(" | ".join(cell.text for cell in row.cells))
            return "\n".join(lines)
        if ext in (".txt", ".md"):
            return content.decode("utf-8")
    except Exception as exc:  # file hỏng → báo rõ, không im lặng
        raise UnreadableDocument(f"Không đọc được file {filename}: {exc}") from exc
    raise UnreadableDocument(f"Định dạng {ext} không hỗ trợ — dùng PDF, DOCX, TXT hoặc MD")
