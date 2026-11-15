"""Chỉ ra một giá trị trích xuất nằm ở đâu trong file người dùng tải lên.

- Mọi loại file: `spans` = [[start, end]] là offset trong `document.text` (giao diện tô sáng đoạn văn bản).
- File OCR (scan/ảnh): thêm `boxes` = khung chữ nhật chuẩn hoá (0..1) trên ảnh từng trang, gom theo dòng.

Giá trị tìm theo bản THÔ mà bộ trích xuất đọc được (chưa chuẩn hoá) — vd "05/01/2027", "0912 345 678".
Nếu mô hình AI diễn đạt lại nên không tìm thấy nguyên văn thì không có nguồn (None), không đoán.
"""

from __future__ import annotations

import re

from src.services.documents import ExtractedText

MAX_VALUE_CHARS = 600
MAX_TEXT_CHARS = 20000  # chặn payload: văn bản trả cho giao diện
BOX_PAD = 0.004  # nới khung một chút cho dễ nhìn

# Hình thức làm việc suy ra từ cụm từ, nên giá trị trích ("full_time") không có trong văn bản
_MODE_PATTERNS = {
    "full_time": r"toàn\s+thời\s+gian|full[-\s]?time",
    "part_time": r"bán\s+thời\s+gian|part[-\s]?time",
}


def _find(text: str, value: str, name: str) -> tuple[int, int] | None:
    if name == "mode":
        pattern = _MODE_PATTERNS.get(value)
    else:
        chars = [re.escape(c) for c in value.strip() if not c.isspace()]
        if not chars or len(chars) > MAX_VALUE_CHARS:
            return None
        # Bỏ qua khoảng trắng/xuống dòng giữa các ký tự: OCR hay ngắt dòng và tách chữ khác bản trích
        pattern = r"\s*".join(chars)
    if not pattern:
        return None
    # Ưu tiên khớp đúng chữ hoa/thường: tên công ty cũng xuất hiện viết hoa ở tiêu đề thư,
    # nhưng giá trị thật nằm ở dòng "Tên công ty: …". Không có thì mới bỏ qua hoa/thường.
    m = re.search(pattern, text) or re.search(pattern, text, re.IGNORECASE)
    return m.span() if m else None


def _boxes(doc: ExtractedText, start: int, end: int) -> list[dict]:
    lines: dict[tuple[int, int], list] = {}
    for w in doc.words:
        if w.end > start and w.start < end:
            lines.setdefault((w.page, w.line), []).append(w)
    boxes = []
    for (page, _), ws in lines.items():
        x0, y0 = min(w.x for w in ws), min(w.y for w in ws)
        x1, y1 = max(w.x + w.w for w in ws), max(w.y + w.h for w in ws)
        boxes.append({
            "page": page,
            "x": round(max(x0 - BOX_PAD, 0), 4), "y": round(max(y0 - BOX_PAD, 0), 4),
            "w": round(min(x1 - x0 + 2 * BOX_PAD, 1), 4), "h": round(min(y1 - y0 + 2 * BOX_PAD, 1), 4),
        })
    return boxes


def locate(doc: ExtractedText, name: str, value: str | None) -> dict | None:
    """Vị trí của `value` trong tài liệu, hoặc None nếu không tìm thấy nguyên văn."""
    if not value:
        return None
    span = _find(doc.text, value, name)
    if span is None or span[0] >= MAX_TEXT_CHARS:
        return None
    start, end = span[0], min(span[1], MAX_TEXT_CHARS)
    source: dict = {"spans": [[start, end]]}
    if doc.words:
        boxes = _boxes(doc, start, end)
        if boxes:
            source["boxes"] = boxes
            source["page"] = boxes[0]["page"]
    return source


def document_payload(doc: ExtractedText) -> dict:
    """Phần `document` trong phản hồi: ảnh từng trang (nếu OCR) và văn bản để đối chiếu."""
    return {
        "kind": "image" if doc.pages else "text",
        "ocr": doc.used_ocr,
        "text": doc.text[:MAX_TEXT_CHARS],
        "truncated": len(doc.text) > MAX_TEXT_CHARS,
        "pages": [{"index": p.index, "width": p.width, "height": p.height, "image": p.image} for p in doc.pages],
    }
