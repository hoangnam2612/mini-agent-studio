"""Đọc text từ PDF / DOCX / TXT / MD / ảnh — dùng chung cho intake (R2.2) và kho quy định (R9).

OCR (Tesseract, chạy cục bộ nên ảnh không rời máy chủ) chỉ bật khi caller truyền ocr=True —
hiện chỉ /intake/extract. Kho quy định cần text layer thật, không âm thầm OCR.

Với OCR, kết quả mang theo bố cục: ảnh xem trước từng trang và toạ độ từng từ (chuẩn hoá 0..1),
đối chiếu theo offset trong `text`, để giao diện chỉ ra giá trị được lấy từ đâu trong file.
"""

from __future__ import annotations

import base64
import io
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from src.config import get_settings

IMAGE_EXTS = (".png", ".jpg", ".jpeg")
MIN_TEXT_CHARS = 30  # PDF có ít chữ hơn ngưỡng này (sau strip) coi như scan → thử OCR
OCR_DPI = 300
MAX_IMAGE_PIXELS = 40_000_000  # chặn ảnh phình to khi giải nén (decompression bomb)
OCR_GOOD_CONFIDENCE = 94.0  # độ tin cậy trung bình của từ đủ tốt thì khỏi thử bản xử lý ảnh thứ hai
PREVIEW_MAX = (1100, 1560)  # ảnh xem trước gửi cho giao diện (JPEG), toạ độ từ vẫn chuẩn hoá nên không lệ thuộc cỡ này

Progress = Callable[[dict], None]


class UnreadableDocument(Exception):  # noqa: N818
    pass


@dataclass
class WordBox:
    """Một từ OCR: [start, end) là offset trong ExtractedText.text; x,y,w,h chuẩn hoá theo cỡ trang (0..1)."""

    start: int
    end: int
    page: int
    line: int  # id dòng, duy nhất trong trang
    x: float
    y: float
    w: float
    h: float


@dataclass
class PagePreview:
    index: int
    width: int
    height: int
    image: str  # data URL JPEG


@dataclass
class ExtractedText:
    text: str
    used_ocr: bool = False
    pages: list[PagePreview] = field(default_factory=list)  # chỉ có khi OCR
    words: list[WordBox] = field(default_factory=list)  # chỉ có khi OCR


def _preview(img, index: int) -> PagePreview:
    rgb = img.convert("RGB")
    size = rgb.size
    rgb.thumbnail(PREVIEW_MAX)
    buf = io.BytesIO()
    rgb.save(buf, format="JPEG", quality=72)
    data = base64.b64encode(buf.getvalue()).decode("ascii")
    return PagePreview(index=index, width=size[0], height=size[1], image=f"data:image/jpeg;base64,{data}")


def _tess_data(image) -> dict:
    """Gọi image_to_data, đổi mọi lỗi Tesseract thành UnreadableDocument có thông báo rõ."""
    try:
        import pytesseract
    except ImportError as exc:
        raise UnreadableDocument("Máy chủ chưa cài thư viện OCR") from exc
    settings = get_settings()
    try:
        return pytesseract.image_to_data(
            image, lang=settings.ocr_lang, timeout=settings.ocr_timeout_seconds, output_type=pytesseract.Output.DICT,
        )
    except pytesseract.TesseractNotFoundError as exc:
        raise UnreadableDocument("Máy chủ chưa cài Tesseract OCR (hoặc gói ngôn ngữ) — hãy nhập tay") from exc
    except RuntimeError as exc:  # pytesseract báo quá thời gian bằng RuntimeError
        raise UnreadableDocument("Đọc chữ từ ảnh quá lâu — hãy tải bản nhỏ/rõ hơn hoặc nhập tay") from exc
    except pytesseract.TesseractError as exc:
        raise UnreadableDocument(f"OCR lỗi: {exc}") from exc


def _mean_conf(data: dict) -> float:
    """Độ tin cậy trung bình (0..100) của các từ Tesseract nhận ra."""
    confs = [float(c) for c, t in zip(data["conf"], data["text"], strict=True) if str(t).strip() and float(c) >= 0]
    return sum(confs) / len(confs) if confs else 0.0


def _layout_from_data(data: dict, size: tuple[int, int], page: int, base: int) -> tuple[str, list[WordBox]]:
    """Dữ liệu image_to_data → (text, các từ). Text dựng từ chính danh sách từ nên offset khớp từng ký tự."""
    width, height = size
    lines: dict[tuple[int, int, int], list[int]] = {}
    for i, raw in enumerate(data["text"]):
        if not str(raw).strip() or float(data["conf"][i]) < 0:
            continue
        lines.setdefault((data["block_num"][i], data["par_num"][i], data["line_num"][i]), []).append(i)

    out: list[str] = []
    words: list[WordBox] = []
    pos = base
    for line_id, idxs in enumerate(lines.values()):
        for n, i in enumerate(idxs):
            token = str(data["text"][i]).strip()
            start = pos
            out.append(token)
            pos += len(token)
            words.append(WordBox(
                start=start, end=pos, page=page, line=line_id,
                x=data["left"][i] / width, y=data["top"][i] / height,
                w=data["width"][i] / width, h=data["height"][i] / height,
            ))
            if n < len(idxs) - 1:
                out.append(" ")
                pos += 1
        out.append("\n")
        pos += 1
    return "".join(out), words


def _layout_page(gray_image, page: int, base: int) -> tuple[str, list[WordBox]]:
    """OCR một ảnh xám → (text, các từ)."""
    return _layout_from_data(_tess_data(gray_image), gray_image.size, page, base)


def _enhance(img):
    """Chuẩn bị ảnh chụp cho OCR (PIL RGB → xám).

    - Lấy kênh đỏ: mực đỏ của dấu mộc gần như biến mất, chữ đen vẫn tối.
    - Bù bóng đổ/ánh sáng không đều: ước lượng nền giấy (ảnh thu nhỏ, lọc max rồi làm mờ) và cộng phần nền bị tối
      vào ảnh, nên giấy về trắng đều còn chữ vẫn đậm.
    """
    from PIL import Image, ImageChops, ImageFilter

    channel = img.split()[0]
    width, height = channel.size
    small = channel.resize((max(width // 8, 1), max(height // 8, 1)), Image.BILINEAR)
    small = small.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(4))
    background = small.resize((width, height), Image.BILINEAR)
    return ImageChops.add(channel, ImageChops.invert(background))


def _ocr_page(img, page: int, base: int) -> tuple[str, list[WordBox]]:
    """OCR một trang (PIL RGB). Thử bản đã xử lý ảnh trước; nếu độ tin cậy chưa tốt thì thử thêm bản xám gốc rồi lấy bản tốt hơn
    (bản xử lý có thể làm hỏng chữ ở vài ảnh scan, nhất là chỗ dấu mộc xám đè lên chữ)."""
    data = _tess_data(_enhance(img))
    conf = _mean_conf(data)
    if conf < OCR_GOOD_CONFIDENCE:
        plain = _tess_data(img.convert("L"))
        if _mean_conf(plain) > conf:
            data = plain
    return _layout_from_data(data, img.size, page, base)


def _ocr_pages(images: list, progress: Progress | None) -> ExtractedText:
    """images: danh sách PIL RGB (đã xoay đúng chiều). Mỗi trang qua _ocr_page (xử lý ảnh + chọn bản đọc tốt hơn)."""
    text_parts: list[str] = []
    words: list[WordBox] = []
    pages: list[PagePreview] = []
    base = 0
    for index, img in enumerate(images):
        if progress:
            progress({"stage": "ocr", "page": index + 1, "pages": len(images)})
        page_text, page_words = _ocr_page(img, index, base)
        text_parts.append(page_text)
        words.extend(page_words)
        pages.append(_preview(img, index))
        base += len(page_text)
    return ExtractedText("".join(text_parts), used_ocr=True, pages=pages, words=words)


def ocr_image(content: bytes, progress: Progress | None = None) -> ExtractedText:
    from PIL import Image, ImageOps

    img = Image.open(io.BytesIO(content))
    if img.width * img.height > MAX_IMAGE_PIXELS:
        raise UnreadableDocument("Ảnh quá lớn — hãy giảm độ phân giải")
    img = ImageOps.exif_transpose(img)  # ảnh chụp điện thoại hay bị xoay theo EXIF
    return _ocr_pages([img.convert("RGB")], progress)


def ocr_pdf(content: bytes, progress: Progress | None = None) -> ExtractedText:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(content)
    count = min(len(pdf), get_settings().ocr_max_pages)
    images = [pdf[index].render(scale=OCR_DPI / 72).to_pil().convert("RGB") for index in range(count)]
    return _ocr_pages(images, progress)


def read_document(filename: str, content: bytes, *, ocr: bool = False, progress: Progress | None = None) -> ExtractedText:
    """Đọc text; ocr=True cho phép dùng OCR với ảnh và PDF scan (khi OCR_ENABLED).

    progress: callback nhận {"stage": "ocr", "page": n, "pages": N} trước mỗi trang OCR (gọi từ thread đang đọc).
    """
    ext = Path(filename).suffix.lower()
    use_ocr = ocr and get_settings().ocr_enabled
    try:
        if ext == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            if use_ocr and len(text.strip()) < MIN_TEXT_CHARS:
                return ocr_pdf(content, progress)
            return ExtractedText(text)
        if ext == ".docx":
            from docx import Document

            doc = Document(io.BytesIO(content))
            lines = [p.text for p in doc.paragraphs]
            for table in doc.tables:
                for row in table.rows:
                    lines.append(" | ".join(cell.text for cell in row.cells))
            return ExtractedText("\n".join(lines))
        if ext in (".txt", ".md"):
            return ExtractedText(content.decode("utf-8"))
        if ext in IMAGE_EXTS and use_ocr:
            return ocr_image(content, progress)
    except UnreadableDocument:
        raise
    except Exception as exc:  # file hỏng → báo rõ, không im lặng
        raise UnreadableDocument(f"Không đọc được file {filename}: {exc}") from exc
    raise UnreadableDocument(f"Định dạng {ext} không hỗ trợ — dùng PDF, DOCX, TXT hoặc MD")


def extract_text(filename: str, content: bytes, *, ocr: bool = False) -> str:
    return read_document(filename, content, ocr=ocr).text
