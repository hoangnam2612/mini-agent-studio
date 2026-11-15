"""Vị trí nguồn của từng trường (provenance) + tiến độ SSE của /intake/extract/stream."""

from __future__ import annotations

import json

from src.services import documents, intake
from src.services.documents import ExtractedText, PagePreview, UnreadableDocument
from src.services.intake import ExtractedFields, FieldGuess
from src.services.provenance import document_payload, locate

LETTER = "Tên công ty: Công ty ABC\nMã số thuế: 0109998887\nĐiện thoại: 0912 345 678\nThời gian: từ ngày 05/01/2027\nđến ngày 30/03/2027, toàn thời gian."


def _tess_dict(lines: list[list[str]], line_h: int = 40, conf: int = 91) -> dict:
    """Dữ liệu giống pytesseract.image_to_data (kèm dòng cấp block/line có conf -1 như thật)."""
    keys = ("text", "conf", "block_num", "par_num", "line_num", "left", "top", "width", "height")
    out: dict[str, list] = {k: [] for k in keys}

    def row(text, conf, line, left, top, width, height):
        for k, v in zip(keys, (text, conf, 1, 1, line, left, top, width, height), strict=True):
            out[k].append(v)

    for n, words in enumerate(lines, start=1):
        row("", -1, n, 0, n * 100, 900, line_h)  # dòng tổng hợp, không có chữ
        left = 50
        for word in words:
            row(word, conf, n, left, n * 100, len(word) * 20, line_h)
            left += len(word) * 20 + 20
    return out


def test_layout_page_offsets_match_words(monkeypatch):
    from PIL import Image

    lines = [["Mã", "số", "thuế:", "0109998887"], ["Điện", "thoại:", "0912", "345", "678"]]
    monkeypatch.setattr(documents, "_tess_data", lambda image: _tess_dict(lines))
    text, words = documents._layout_page(Image.new("L", (1000, 2000)), page=0, base=0)
    assert text == "Mã số thuế: 0109998887\nĐiện thoại: 0912 345 678\n"
    assert [text[w.start:w.end] for w in words] == [w for line in lines for w in line]
    first = words[0]  # chuẩn hoá theo cỡ ảnh 1000x2000
    assert (first.x, first.y) == (50 / 1000, 100 / 2000) and first.page == 0

    # trang sau: offset cộng dồn theo base
    _, more = documents._layout_page(Image.new("L", (1000, 2000)), page=1, base=len(text))
    assert more[0].start == len(text) and more[0].page == 1


def _doc(monkeypatch, lines: list[list[str]]) -> ExtractedText:
    from PIL import Image

    monkeypatch.setattr(documents, "_tess_data", lambda image: _tess_dict(lines))
    text, words = documents._layout_page(Image.new("L", (1000, 2000)), 0, 0)
    return ExtractedText(text, used_ocr=True, words=words)


def test_locate_returns_text_span_and_boxes(monkeypatch):
    doc = _doc(monkeypatch, [["Mã", "số", "thuế:", "0109998887"], ["Điện", "thoại:", "0912", "345", "678"]])
    src = locate(doc, "company_tax_code", "0109998887")
    start, end = src["spans"][0]
    assert doc.text[start:end] == "0109998887" and len(src["boxes"]) == 1 and src["page"] == 0
    box = src["boxes"][0]
    assert 0 <= box["x"] <= 1 and 0 <= box["y"] <= 1 and box["w"] > 0 and box["h"] > 0

    # SĐT viết liền, văn bản có dấu cách → vẫn tìm thấy
    phone = locate(doc, "mentor_phone", "0912345678")
    assert doc.text[phone["spans"][0][0]:phone["spans"][0][1]] == "0912 345 678"


def test_locate_value_across_lines_gives_box_per_line(monkeypatch):
    doc = _doc(monkeypatch, [["từ", "ngày", "05/01/2027"], ["đến", "ngày", "30/03/2027,", "toàn", "thời", "gian."]])
    src = locate(doc, "start_date", "05/01/2027 đến ngày 30/03/2027")
    assert len(src["boxes"]) == 2
    mode = locate(doc, "mode", "full_time")
    assert doc.text[mode["spans"][0][0]:mode["spans"][0][1]] == "toàn thời gian"
    assert locate(doc, "company_name", "Công ty không có trong file") is None
    assert locate(doc, "company_name", None) is None


def test_locate_prefers_exact_case_over_uppercase_title():
    text = "CÔNG TY TNHH SAO MAI\nTên công ty: Công ty TNHH Sao Mai\n"
    start, end = locate(ExtractedText(text), "company_name", "Công ty TNHH Sao Mai")["spans"][0]
    assert text[start:end] == "Công ty TNHH Sao Mai" and start > text.index("\n")
    # chỉ có bản viết hoa → vẫn tìm được (bỏ qua hoa/thường)
    only_upper = ExtractedText("CÔNG TY TNHH SAO MAI\n")
    assert locate(only_upper, "company_name", "Công ty TNHH Sao Mai") is not None


def test_locate_text_document_has_spans_without_boxes():
    doc = ExtractedText(LETTER)
    src = locate(doc, "company_tax_code", "0109998887")
    assert doc.text[src["spans"][0][0]:src["spans"][0][1]] == "0109998887" and "boxes" not in src


def test_annotate_sources_keeps_raw_even_when_invalid(db):
    text = "Mã số thuế: 0101234567\nNgày bắt đầu: 31/02/2027"
    extracted = intake.regex_extract(text)
    result = intake.build_suggestions(db, extracted, source="rules")
    intake.annotate_sources(result, extracted, ExtractedText(text))
    tax = result["fields"]["company_tax_code"]
    assert tax["raw"] == "0101234567" and text[tax["source"]["spans"][0][0]:tax["source"]["spans"][0][1]] == "0101234567"
    # ngày không hợp lệ: bị loại (cần nhập tay) nhưng vẫn cho thấy đọc ra gì, ở đâu
    start = result["fields"]["start_date"]
    assert start["needs_manual"] and start["raw"] == "31/02/2027" and "source" in start
    # trường không đọc được: không có raw/source
    assert "raw" not in result["fields"]["position"] and "source" not in result["fields"]["position"]
    # khớp catalog đổi giá trị nhưng nguồn vẫn là chỗ đọc được trong file
    assert result["matched_company"] is not None


def test_document_payload_caps_text_and_lists_pages():
    pages = [PagePreview(0, 800, 1100, "data:image/jpeg;base64,AAAA")]
    payload = document_payload(ExtractedText("x" * 25000, used_ocr=True, pages=pages))
    assert payload["kind"] == "image" and payload["truncated"] and len(payload["text"]) == 20000
    assert payload["pages"][0]["image"].startswith("data:image/jpeg")
    assert document_payload(ExtractedText("abc"))["kind"] == "text"


# ---------------------------------------------------------------- SSE tiến độ

def _events(raw: str) -> list[dict]:
    return [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]


async def _stream(api, filename: str, content: bytes, mime: str):
    headers = await api.login("sv01")
    async with api.client.stream("POST", "/api/v1/intake/extract/stream", headers=headers,
                                 files={"file": (filename, content, mime)}) as r:
        status = r.status_code
        raw = "".join([chunk async for chunk in r.aiter_text()])
    return status, raw


async def test_stream_reports_stages_then_result_with_sources(api, monkeypatch):
    def fake_ocr(content, progress=None):
        for page in (1, 2):
            if progress:
                progress({"stage": "ocr", "page": page, "pages": 2})
        return ExtractedText(LETTER, used_ocr=True, pages=[PagePreview(0, 100, 140, "data:image/jpeg;base64,AAAA")])

    monkeypatch.setattr(documents, "ocr_image", fake_ocr)
    status, raw = await _stream(api, "scan.png", b"\x89PNG\r\n\x1a\n" + b"0" * 16, "image/png")
    assert status == 200
    events = _events(raw)
    stages = [(e["stage"], e.get("page")) for e in events if e["type"] == "stage"]
    assert stages == [("upload", None), ("read", None), ("ocr", 1), ("ocr", 2), ("extract", None)]
    done = events[-1]
    assert done["type"] == "done"
    result = done["result"]
    assert result["ocr"] is True and result["document"]["kind"] == "image" and len(result["document"]["pages"]) == 1
    tax = result["fields"]["company_tax_code"]
    start, end = tax["source"]["spans"][0]
    assert result["document"]["text"][start:end] == "0109998887"


async def test_stream_text_file_has_no_ocr_stage(api):
    status, raw = await _stream(api, "thu.txt", LETTER.encode(), "text/plain")
    events = _events(raw)
    assert status == 200 and [e["stage"] for e in events if e["type"] == "stage"] == ["upload", "read", "extract"]
    assert events[-1]["result"]["document"]["kind"] == "text" and events[-1]["result"]["ocr"] is False


async def test_stream_errors_are_explicit(api, monkeypatch):
    def boom(content, progress=None):
        raise UnreadableDocument("Máy chủ chưa cài Tesseract OCR")

    monkeypatch.setattr(documents, "ocr_image", boom)
    status, raw = await _stream(api, "scan.jpg", b"\xff\xd8\xff" + b"0" * 16, "image/jpeg")
    events = _events(raw)
    assert status == 200 and events[-1] == {"type": "error", "detail": "Máy chủ chưa cài Tesseract OCR"}
    # file sai định dạng bị từ chối bằng HTTP 422 trước khi mở stream
    status, _ = await _stream(api, "a.exe", b"MZ", "application/x-msdownload")
    assert status == 422
    # chưa đăng nhập
    r = await api.client.post("/api/v1/intake/extract/stream", files={"file": ("a.txt", b"x", "text/plain")})
    assert r.status_code == 401


# ---------------------------------------------------------------- regex trước, LLM chỉ lấp chỗ thiếu


PROSE = (
    "Công ty Cổ phần Ánh Dương trân trọng thông báo tiếp nhận sinh viên.\n"
    "Mã số thuế: 0109998887\n"
    "Vị trí: Thực tập sinh dữ liệu\n"
    "Điện thoại: 0912 345 678, email: lan@anhduong.vn\n"
    "Thực tập bắt đầu vào ngày 5 tháng 1 năm 2027 và kết thúc ngày 30 tháng 3 năm 2027, làm việc toàn thời gian.\n"
)
FULL_LETTER = (
    "Tên công ty: Công ty ABC\nMã số thuế: 0109998887\nĐịa chỉ: 1 Phố Huế, Hà Nội\nVị trí thực tập: Backend\n"
    "Mô tả công việc: Viết API\nNgười hướng dẫn: Ông Bảo\nEmail liên hệ bao@abc.vn, điện thoại 0912 345 678\n"
    "Thời gian: từ ngày 05/01/2027 đến ngày 30/03/2027, toàn thời gian.\n"
)


def _llm(monkeypatch, fake):
    calls: list[tuple[str, list[str]]] = []

    async def wrapper(text, fields):
        calls.append((text, list(fields)))
        return await fake(text, fields)

    monkeypatch.setattr(intake, "llm_available", lambda: True)
    monkeypatch.setattr(intake, "llm_extract", wrapper)
    return calls


async def test_llm_not_called_when_regex_found_everything(db, monkeypatch):
    async def fake(text, fields):
        raise AssertionError("không được gọi LLM khi regex đã đủ")

    calls = _llm(monkeypatch, fake)
    result = await intake.extract_suggestions(db, FULL_LETTER)
    assert calls == [] and result["source"] == "rules"
    assert result["llm"] == {"available": True, "requested": [], "accepted": [], "error": None}
    assert all(not f["needs_manual"] and f["by"] == "rules" and "source" in f for f in result["fields"].values())


async def test_llm_only_asked_for_missing_fields_on_redacted_text(db, monkeypatch):
    async def fake(text, fields):
        return ExtractedFields(
            company_name=FieldGuess(value="Công ty Cổ phần Ánh Dương", confidence=0.9, quote="Công ty Cổ phần Ánh Dương"),
            # ngày viết bằng chữ: value chuẩn dd/mm/yyyy không có trong file, quote thì có
            start_date=FieldGuess(value="05/01/2027", confidence=0.9, quote="ngày 5 tháng 1 năm 2027"),
            end_date=FieldGuess(value="30/03/2027", confidence=0.9, quote="ngày 30 tháng 3 năm 2027"),
            company_address=FieldGuess(value="Hà Nội", confidence=0.9),  # bịa: không có trong file
            company_tax_code=FieldGuess(value="9999999999", confidence=0.9),  # không được hỏi → bỏ qua
            position=FieldGuess(value="Giám đốc", confidence=0.9, quote="Giám đốc"),  # regex đã có → bỏ qua
        )

    calls = _llm(monkeypatch, fake)
    result = await intake.extract_suggestions(db, PROSE)
    (sent, asked), = calls
    assert asked == ["company_name", "company_address", "job_description", "start_date", "end_date", "mentor_name"]
    # văn bản gửi LLM đã che MST, SĐT, email
    assert "0109998887" not in sent and "lan@anhduong.vn" not in sent and "0912" not in sent
    f = result["fields"]
    name = f["company_name"]
    assert name["by"] == "llm" and name["value"] == "Công ty Cổ phần Ánh Dương"
    s, e = name["source"]["spans"][0]
    assert PROSE[s:e] == "Công ty Cổ phần Ánh Dương"
    s, e = f["start_date"]["source"]["spans"][0]
    assert f["start_date"]["value"] == "2027-01-05" and PROSE[s:e] == "ngày 5 tháng 1 năm 2027"
    assert f["end_date"]["value"] == "2027-03-30"
    # giá trị LLM không tìm thấy trong file → loại, báo `unverified`
    assert f["company_address"]["needs_manual"] and f["company_address"]["unverified"] == "Hà Nội"
    assert "source" not in f["company_address"]
    # trường không hỏi giữ nguyên kết quả regex
    assert f["company_tax_code"]["value"] == "0109998887" and f["company_tax_code"]["by"] == "rules"
    assert f["position"]["value"] == "Thực tập sinh dữ liệu"
    assert result["source"] == "rules+llm"
    assert set(result["llm"]["accepted"]) == {"company_name", "start_date", "end_date"}


async def test_llm_failure_keeps_regex_and_reports_error(db, monkeypatch):
    async def fake(text, fields):
        raise RuntimeError("401 key hết hạn sk-secret")

    _llm(monkeypatch, fake)
    result = await intake.extract_suggestions(db, PROSE)
    assert result["source"] == "rules" and result["fields"]["position"]["value"] == "Thực tập sinh dữ liệu"
    assert result["llm"]["error"] == "RuntimeError" and result["llm"]["accepted"] == []
    assert "sk-secret" not in json.dumps(result)  # không lộ chi tiết lỗi nhà cung cấp


async def test_llm_not_asked_when_only_sensitive_fields_missing(db, monkeypatch):
    async def fake(text, fields):
        raise AssertionError("MST/email/SĐT đã bị che, hỏi LLM vô ích")

    calls = _llm(monkeypatch, fake)
    text = "\n".join(line for line in FULL_LETTER.splitlines() if "thuế" not in line and "Email" not in line)
    result = await intake.extract_suggestions(db, text)
    assert calls == [] and result["fields"]["company_tax_code"]["needs_manual"]
    assert result["llm"]["requested"] == []


async def test_without_llm_missing_fields_stay_manual(db, monkeypatch):
    monkeypatch.setattr(intake, "llm_available", lambda: False)
    result = await intake.extract_suggestions(db, PROSE)
    assert result["llm"]["available"] is False and result["llm"]["requested"] == []
    assert result["fields"]["company_name"]["needs_manual"]


# ---------------------------------------------------------------- tiền xử lý ảnh và chọn bản đọc tốt hơn

def test_enhance_evens_out_shadow_and_drops_red_stamp():
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (800, 600), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 399, 599), fill=(170, 170, 170))  # nửa trái trong bóng đổ
    for x0 in (60, 560):
        draw.rectangle((x0, 100, x0 + 90, 112), fill=(0, 0, 0))  # nét chữ ở cả hai nửa
    draw.ellipse((300, 300, 380, 380), fill=(200, 30, 40))  # mực đỏ của dấu mộc
    out = documents._enhance(img)
    assert out.mode == "L" and out.size == img.size
    assert out.getpixel((200, 450)) >= 235 and out.getpixel((700, 450)) >= 235  # nền về trắng đều, kể cả chỗ bóng
    assert out.getpixel((100, 106)) < 100 and out.getpixel((600, 106)) < 100  # chữ vẫn đậm
    assert out.getpixel((340, 340)) > 150 > img.convert("L").getpixel((340, 340))  # dấu đỏ nhạt đi so với chuyển xám thường


def _page_with(monkeypatch, confs: list[int]):
    from PIL import Image

    calls: list[int] = []

    def fake(image):
        calls.append(len(calls))
        return _tess_dict([[f"ban{len(calls)}"]], conf=confs[len(calls) - 1])

    monkeypatch.setattr(documents, "_tess_data", fake)
    text, _ = documents._ocr_page(Image.new("RGB", (400, 600), "white"), page=0, base=0)
    return text, calls


def test_ocr_page_keeps_first_pass_when_confident(monkeypatch):
    text, calls = _page_with(monkeypatch, [96, 99])
    assert text == "ban1\n" and len(calls) == 1  # đủ tin cậy: khỏi tốn lượt OCR thứ hai


def test_ocr_page_picks_better_variant_when_unsure(monkeypatch):
    text, calls = _page_with(monkeypatch, [80, 93])
    assert text == "ban2\n" and len(calls) == 2  # bản xám gốc đọc tốt hơn → dùng bản đó
    text, calls = _page_with(monkeypatch, [90, 85])
    assert text == "ban1\n" and len(calls) == 2  # bản đã xử lý vẫn tốt hơn → giữ nguyên
