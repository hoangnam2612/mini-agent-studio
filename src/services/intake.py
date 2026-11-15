"""Intake Extractor (R2.2–2.3, R2.6) — trích xuất giấy tiếp nhận thành GỢI Ý có độ tin cậy.

Luồng: regex xác định chạy trước trên văn bản gốc. Chỉ khi còn trường thiếu (và có LLM) thì văn bản
được che PII rồi gửi LLM, và LLM chỉ được hỏi đúng các trường thiếu. Email/SĐT/mã số thuế không bao giờ
hỏi LLM (đã bị che; chỉ lấy từ regex). Mọi giá trị — của regex lẫn LLM — phải tìm thấy được trong file
(để giao diện tô sáng cho người dùng đối chiếu); giá trị LLM không có trong file bị loại.
Trường có độ tin cậy < 0.5 bị bỏ trống, đánh dấu "cần nhập tay".
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import date, datetime

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.agents.prompts import load_prompt
from src.models.orm import Company
from src.services.documents import ExtractedText
from src.services.llm import get_llm, llm_available
from src.services.pii import Redactor
from src.services.provenance import locate

FIELDS = (
    "company_name", "company_tax_code", "company_address", "position", "job_description",
    "start_date", "end_date", "mentor_name", "mentor_email", "mentor_phone", "mode",
)
MIN_CONFIDENCE = 0.5
OCR_CONFIDENCE_FACTOR = 0.85  # OCR có thể nhầm chữ số (0/O, 1/l) → hạ độ tin cậy
logger = logging.getLogger(__name__)

# Bị che trước khi gửi LLM → không hỏi LLM, chỉ lấy từ regex trên văn bản gốc
SENSITIVE_FIELDS = ("company_tax_code", "mentor_email", "mentor_phone")
FIELD_HINTS = {
    "company_name": "tên công ty / doanh nghiệp tiếp nhận sinh viên",
    "company_address": "địa chỉ công ty",
    "position": "vị trí / chức danh thực tập",
    "job_description": "mô tả / nội dung công việc",
    "start_date": "ngày bắt đầu thực tập",
    "end_date": "ngày kết thúc thực tập",
    "mentor_name": "người hướng dẫn tại doanh nghiệp",
    "mode": "hình thức làm việc: full_time hoặc part_time",
}


class FieldGuess(BaseModel):
    value: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    quote: str | None = None  # chỉ LLM điền: đoạn NGUYÊN VĂN trong file chứa giá trị (để tô sáng/xác minh)


class ExtractedFields(BaseModel):
    company_name: FieldGuess = FieldGuess()
    company_tax_code: FieldGuess = FieldGuess()
    company_address: FieldGuess = FieldGuess()
    position: FieldGuess = FieldGuess()
    job_description: FieldGuess = FieldGuess()
    start_date: FieldGuess = FieldGuess()
    end_date: FieldGuess = FieldGuess()
    mentor_name: FieldGuess = FieldGuess()
    mentor_email: FieldGuess = FieldGuess()
    mentor_phone: FieldGuess = FieldGuess()
    mode: FieldGuess = FieldGuess()


# ---------------------------------------------------------------- trích xuất bằng luật (chịu nhiễu OCR)
# Chữ OCR từ ảnh chụp hay: mất dấu, mất một phần nhãn, thêm ký tự rác đầu dòng, ngắt dòng giữa ngày, nhầm O↔0, l↔1.
# Nên nhãn khớp trên bản đã bỏ dấu và không dựa vào nhãn cho các giá trị có hình dạng đặc trưng (MST, ngày, loại hình công ty).

_DIGIT_FIX = str.maketrans("OoIlSB", "001158")  # trong một dãy số, các chữ này gần như chắc chắn là chữ số bị đọc nhầm
_TAX_TOKEN = r"[0-9OoIlSB]{10}(?:[ \t]*-[ \t]*[0-9OoIlSB]{3})?"
_DATE = r"(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{4})"
_DATE_WORDS = r"(\d{1,2})\s*thang\s*(\d{1,2})\s*nam\s*(\d{4})"  # "5 tháng 1 năm 2027" (bản đã bỏ dấu)
_DATE_ANY = r"\d{1,2}\s*(?:[/.\-]\s*\d{1,2}\s*[/.\-]|thang\s*\d{1,2}\s*nam)\s*\d{4}"
_LEGAL = r"(?:tnhh|co\s+phan|cp|mtv|trach\s+nhiem|hop\s+danh|tu\s+nhan|jsc|ltd)"  # loại hình doanh nghiệp (bản bỏ dấu)
_SEP = r"[ \t]*[:;|][ \t]*(?:[-–—|:;][ \t]*)*"
MAX_COMPANY_WORDS = 11  # tên công ty dài hơn thế thường là một câu → để LLM xử lý


def _fold(text: str) -> str:
    """Chữ thường, bỏ dấu; mỗi ký tự vào cho đúng một ký tự ra nên vị trí trên bản này cũng là vị trí trên văn bản gốc."""
    out = []
    for ch in text:
        if ch in "đĐ":
            out.append("d")
            continue
        base = unicodedata.normalize("NFD", ch)[:1] or ch
        out.append(base.lower()[:1] or ch)
    return "".join(out)


def _digit_count(token: str) -> int:
    return sum(c.isdigit() for c in token)


def _labeled(text: str, folded: str, labels: str) -> str | None:
    """Giá trị đứng sau nhãn. `labels` viết không dấu; khớp trên `folded`, lấy giá trị từ `text` cùng vị trí.

    Chịu ký tự rác đầu dòng ("_ ", "' ", "/\\ ") và nhãn bị mất dấu. Giá trị phải nằm cùng dòng với nhãn.
    """
    m = re.search(rf"(?m)^[\W_]*(?:{labels}){_SEP}(.+?)[ \t]*$", folded)
    return text[m.start(1):m.end(1)].strip() if m else None


def _tax_code(text: str, folded: str) -> tuple[str | None, float]:
    """(giá trị thô, độ tin cậy). Sau nhãn "Mã số thuế"/"MST" (nhãn có thể mất chữ "Mã") → 0.9.
    Nhãn mất hẳn: nhận dãy 10 hoặc 13 chữ số đứng riêng, trừ dòng của số điện thoại → 0.6."""
    label = re.search(r"\b(?:(?:ma\s+)?so\s+thue|mst)\b", folded)
    if label:
        end = text.find("\n", label.end())
        rest = text[label.end(): end if end >= 0 else len(text)]
        for m in re.finditer(_TAX_TOKEN, rest):
            if _digit_count(m.group(0)) >= 7:
                return m.group(0), 0.9
    for m in re.finditer(r"(?<![0-9A-Za-z])\d{10}(?:-\d{3})?(?![0-9A-Za-z])", text):
        start = text.rfind("\n", 0, m.start()) + 1
        end = text.find("\n", m.end())
        if re.search(r"dien\s+thoai|sdt|phone|\btel\b|di\s+dong", folded[start: end if end >= 0 else len(text)]):
            continue
        return m.group(0), 0.6
    return None, 0.0


def _company_by_form(text: str, folded: str) -> tuple[str | None, float]:
    """Không có nhãn tên công ty: tìm dòng "Công ty/Cty + loại hình (TNHH, Cổ phần…)". Dòng viết hoa-thường lẫn lộn
    (giá trị) được ưu tiên hơn dòng IN HOA (tiêu đề thư)."""
    found = []
    for m in re.finditer(rf"(?:cong\s+ty|cty)\s+{_LEGAL}\b[^\n]*", folded):
        raw = text[m.start():m.end()].strip(" .,;|-")
        if len(raw.split()) > MAX_COMPANY_WORDS:  # cả câu văn xuôi ("Công ty X trân trọng thông báo…") chứ không phải tên
            continue
        found.append((raw != raw.upper(), raw))
    for mixed, raw in found:
        if mixed:
            return raw, 0.7
    return (found[0][1], 0.6) if found else (None, 0.0)


def regex_extract(text: str) -> ExtractedFields:
    """Bộ trích xuất xác định — chạy trước; LLM (nếu có) chỉ lấp các trường còn thiếu."""
    out = ExtractedFields()
    text = unicodedata.normalize("NFC", text)
    folded = _fold(text)

    def put(name: str, value: str | None, conf: float) -> None:
        if value:
            setattr(out, name, FieldGuess(value=value.strip(" .;"), confidence=conf))

    company = _labeled(text, folded, r"ten\s+(?:cong\s+ty|doanh\s+nghiep)|cong\s+ty|doanh\s+nghiep|don\s+vi\s+tiep\s+nhan")
    if company:
        put("company_name", company, 0.85)
    else:
        put("company_name", *_company_by_form(text, folded))
    tax, tax_conf = _tax_code(text, folded)
    put("company_tax_code", tax, tax_conf)
    put("company_address", _labeled(text, folded, r"dia\s+chi(?:\s+(?:cong\s+ty|doanh\s+nghiep))?"), 0.8)
    put("position", _labeled(text, folded, r"vi\s+tri(?:\s+thuc\s+tap)?|tri\s+thuc\s+tap|chuc\s+danh"), 0.8)
    put("job_description", _labeled(text, folded, r"mo\s+ta\s+cong\s+viec|noi\s+dung\s+cong\s+viec|nhiem\s+vu"), 0.7)
    put("mentor_name", _labeled(text, folded, r"nguoi\s+huong\s+dan|can\s+bo\s+huong\s+dan"), 0.8)

    email = re.search(r"[\w.+-]+@[\w-]+(\.[\w-]+)+", text)
    put("mentor_email", email.group(0) if email else None, 0.75)
    # Ưu tiên số đứng sau nhãn điện thoại — số 10 chữ số bắt đầu bằng 0 có thể là mã số thuế
    phone = re.search(r"(?:dien\s+thoai|sdt|dt|di\s+dong|phone|tel)[ \t]*[:;]?[ \t]*((?:\+84|0)(?:[ \t.\-]?\d){9,10})", folded)
    if phone:
        put("mentor_phone", text[phone.start(1):phone.end(1)], 0.8)
    else:
        tax_digits = re.sub(r"\D", "", normalize_tax_code(tax) or "")
        for m in re.finditer(r"(?<!\d)(?:\+84|0)(?:\s?[.-]?\d){9,10}(?!\d)", text):
            if re.sub(r"\D", "", m.group(0)) != tax_digits:
                put("mentor_phone", m.group(0), 0.6)
                break

    # "từ ngày 05/01/2027 đến ngày 30/03/2027" — chịu ngắt dòng giữa ngày và ngày viết bằng chữ ("5 tháng 1 năm 2027").
    # Giá trị thô lấy nguyên văn từ file để tô sáng đúng chỗ; normalize_date đổi sang ISO.
    period = re.search(rf"\btu\s+(?:ngay\s+)?({_DATE_ANY})\s+den\s+(?:ngay\s+)?({_DATE_ANY})", folded)
    if period:
        put("start_date", text[period.start(1):period.end(1)], 0.85)
        put("end_date", text[period.start(2):period.end(2)], 0.85)
    else:
        put("start_date", _labeled(text, folded, r"ngay\s+bat\s+dau"), 0.8)
        put("end_date", _labeled(text, folded, r"ngay\s+ket\s+thuc"), 0.8)

    if re.search(r"ban\s+thoi\s+gian|part[-\s]?time", folded):
        put("mode", "part_time", 0.8)
    elif re.search(r"toan\s+thoi\s+gian|full[-\s]?time", folded):
        put("mode", "full_time", 0.8)
    return out


async def llm_extract(text: str, fields: list[str]) -> ExtractedFields:
    """Hỏi LLM đúng các trường `fields`. `text` phải là văn bản ĐÃ che PII."""
    wanted = "\n".join(f"- {name}: {FIELD_HINTS[name]}" for name in fields)
    prompt = load_prompt("intake_extract.md").replace("{{fields}}", wanted).replace("{{document}}", text[:12000])
    llm = get_llm("classify").with_structured_output(ExtractedFields)
    return await llm.ainvoke(prompt)


# ---------------------------------------------------------------- normalize (R2.3)

def normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    folded = _fold(value)
    m = re.search(_DATE, folded) or re.search(_DATE_WORDS, folded)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            return None
    try:
        return datetime.fromisoformat(value.strip()[:10]).date().isoformat()
    except ValueError:
        return None


def normalize_phone(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if digits.startswith("84"):
        digits = "0" + digits[2:]
    return digits if re.fullmatch(r"0\d{9,10}", digits) else None


def normalize_tax_code(value: str | None) -> str | None:
    if not value:
        return None
    m = re.search(_TAX_TOKEN, value)
    if not m or _digit_count(m.group(0)) < 7:  # ít chữ số thật → không phải mã số thuế
        return None
    return re.sub(r"\s+", "", m.group(0)).translate(_DIGIT_FIX)


def normalize_email(value: str | None) -> str | None:
    if not value:
        return None
    m = re.search(r"[\w.+-]+@[\w-]+(\.[\w-]+)+", value)
    return m.group(0).lower() if m else None


def normalize_company_name(value: str | None) -> str | None:
    if not value:
        return None
    name = re.sub(r"\s+", " ", value).strip(" .,;")
    return re.sub(r"(?i)^cty\b", "Công ty", name)


_NORMALIZERS = {
    "start_date": normalize_date,
    "end_date": normalize_date,
    "mentor_phone": normalize_phone,
    "company_tax_code": normalize_tax_code,
    "mentor_email": normalize_email,
    "company_name": normalize_company_name,
}


def _finalize_field(name: str, guess: FieldGuess, from_ocr: bool = False) -> dict:
    """Chuẩn hoá một trường + áp ngưỡng tin cậy → {value, confidence, needs_manual}."""
    if from_ocr:
        guess = FieldGuess(value=guess.value, confidence=round(guess.confidence * OCR_CONFIDENCE_FACTOR, 2))
    value = guess.value
    if value is not None and name in _NORMALIZERS:
        value = _NORMALIZERS[name](value)
    if name == "mode" and value not in ("full_time", "part_time"):
        value = None
    if value is None or guess.confidence < MIN_CONFIDENCE:
        return {"value": None, "confidence": guess.confidence, "needs_manual": True}
    return {"value": value, "confidence": guess.confidence, "needs_manual": False}


def build_suggestions(db: Session, extracted: ExtractedFields, source: str, from_ocr: bool = False) -> dict:
    """Ghép kết quả trích xuất + chuẩn hóa + khớp DN theo mã số thuế.

    from_ocr: văn bản đến từ OCR (có thể đọc sai chữ số) → giảm độ tin cậy mọi trường.
    """
    fields = {name: _finalize_field(name, getattr(extracted, name), from_ocr) for name in FIELDS}

    matched = None
    tax = fields["company_tax_code"]["value"]
    if tax:
        company = db.scalar(select(Company).where(Company.tax_code == tax))
        if company:
            matched = {"id": company.id, "name": company.name}
            fields["company_name"] = {"value": company.name, "confidence": 1.0, "needs_manual": False}
            if company.address:
                fields["company_address"] = {"value": company.address, "confidence": 1.0, "needs_manual": False}
    return {"fields": fields, "matched_company": matched, "source": source, "ocr": from_ocr,
            "label": "Gợi ý của AI — hãy kiểm tra trước khi nộp"}


def annotate_sources(result: dict, extracted: ExtractedFields, doc: ExtractedText) -> None:
    """Gắn vào từng trường của regex: `raw` (giá trị đọc được, chưa chuẩn hoá), `source` (vị trí trong file), `by`.

    Trường không hợp lệ sau chuẩn hoá (needs_manual) vẫn có `raw` + `source` để người dùng thấy
    hệ thống đã đọc ra gì ở đâu và vì sao bị loại.
    """
    for name in FIELDS:
        raw = getattr(extracted, name).value
        if not raw:
            continue
        entry = result["fields"][name]
        entry["raw"] = raw
        entry["by"] = "rules"
        source = locate(doc, name, raw)
        if source:
            entry["source"] = source


def merge_llm(result: dict, guessed: ExtractedFields, requested: list[str], doc: ExtractedText,
              from_ocr: bool) -> list[str]:
    """Nhận kết quả LLM cho các trường đã hỏi; trả tên các trường được nhận (có giá trị hợp lệ).

    Một giá trị LLM chỉ được dùng khi tìm thấy trong file (nguyên văn giá trị, hoặc đoạn `quote` LLM chép
    lại) — để người dùng đối chiếu được. Không tìm thấy → loại, chỉ ghi `unverified` cho giao diện báo.
    Trường không được hỏi thì bỏ qua, kể cả khi LLM trả về.
    """
    accepted: list[str] = []
    for name in requested:
        guess: FieldGuess = getattr(guessed, name)
        if not guess.value or not guess.value.strip():
            continue
        source = locate(doc, name, guess.value) or locate(doc, name, guess.quote)
        if source is None:
            result["fields"][name]["unverified"] = guess.value
            continue
        field = _finalize_field(name, FieldGuess(value=guess.value, confidence=guess.confidence), from_ocr)
        field.update(raw=guess.quote or guess.value, source=source, by="llm")
        result["fields"][name] = field
        if not field["needs_manual"]:
            accepted.append(name)
    return accepted


async def extract_suggestions(db: Session, text: str, redactor: Redactor | None = None,
                              from_ocr: bool = False, doc: ExtractedText | None = None) -> dict:
    """Regex trước; thiếu trường (và có LLM) mới che PII → hỏi LLM đúng các trường thiếu.

    Kết quả mỗi trường có thể kèm `raw`, `source` (vị trí trong file) và `by` ("rules" | "llm").
    `llm` mô tả lần gọi: available, requested, accepted, error (chỉ tên loại lỗi, không lộ chi tiết nhà cung cấp).
    """
    doc = doc or ExtractedText(text)
    baseline = regex_extract(text)
    result = build_suggestions(db, baseline, source="rules", from_ocr=from_ocr)
    annotate_sources(result, baseline, doc)

    # MST/email/SĐT đã bị che nên LLM không đọc được → không hỏi, dù đang thiếu
    requested = [n for n in FIELDS if n not in SENSITIVE_FIELDS and result["fields"][n]["needs_manual"]]
    llm_info: dict = {"available": llm_available(), "requested": [], "accepted": [], "error": None}
    if requested and llm_info["available"]:
        llm_info["requested"] = requested
        try:
            guessed = await llm_extract((redactor or Redactor()).redact(text), requested)
            llm_info["accepted"] = merge_llm(result, guessed, requested, doc, from_ocr)
        except Exception as exc:  # LLM lỗi → giữ kết quả regex, không chặn SV nhưng báo rõ cho giao diện
            logger.warning("Intake LLM lỗi (%s) — dùng kết quả regex", type(exc).__name__)
            llm_info["error"] = type(exc).__name__
    if llm_info["accepted"]:
        result["source"] = "rules+llm"
    result["llm"] = llm_info
    return result
