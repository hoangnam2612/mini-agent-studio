"""Intake Extractor (R2.2–2.3, R2.6) — trích xuất giấy tiếp nhận thành GỢI Ý có độ tin cậy.

Không có LLM: bộ trích xuất regex xác định. Có LLM: văn bản được che PII (email, SĐT,
mã số thuế, thông tin của chính SV) rồi mới gửi đi; email/SĐT/mã số thuế luôn lấy từ
regex trên văn bản gốc. Trường có độ tin cậy < 0.5 bị bỏ trống, đánh dấu "cần nhập tay".
"""

from __future__ import annotations

import re
from datetime import date, datetime

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.agents.prompts import load_prompt
from src.models.orm import Company
from src.services.llm import get_llm, llm_available
from src.services.pii import Redactor

FIELDS = (
    "company_name", "company_tax_code", "company_address", "position", "job_description",
    "start_date", "end_date", "mentor_name", "mentor_email", "mentor_phone", "mode",
)
MIN_CONFIDENCE = 0.5


class FieldGuess(BaseModel):
    value: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


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


def _labeled(text: str, labels: str) -> str | None:
    m = re.search(rf"(?im)^\s*[-•*]?\s*(?:{labels})\s*[:：]\s*(.+?)\s*$", text)
    return m.group(1).strip() if m else None


_DATE = r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})"


def regex_extract(text: str) -> ExtractedFields:
    """Bộ trích xuất xác định — chạy khi không có LLM, và là baseline để test."""
    out = ExtractedFields()

    def put(name: str, value: str | None, conf: float) -> None:
        if value:
            setattr(out, name, FieldGuess(value=value.strip(" .;"), confidence=conf))

    put("company_name", _labeled(text, r"tên\s+(?:công\s+ty|doanh\s+nghiệp)|công\s+ty|doanh\s+nghiệp|đơn\s+vị\s+tiếp\s+nhận"), 0.85)
    tax = _labeled(text, r"mã\s+số\s+thuế|mst")
    put("company_tax_code", tax, 0.9)
    put("company_address", _labeled(text, r"địa\s+chỉ(?:\s+(?:công\s+ty|doanh\s+nghiệp))?"), 0.8)
    put("position", _labeled(text, r"vị\s+trí(?:\s+thực\s+tập)?|chức\s+danh"), 0.8)
    put("job_description", _labeled(text, r"mô\s+tả\s+công\s+việc|nội\s+dung\s+công\s+việc|nhiệm\s+vụ"), 0.7)
    put("mentor_name", _labeled(text, r"người\s+hướng\s+dẫn|cán\s+bộ\s+hướng\s+dẫn"), 0.8)

    email = re.search(r"[\w.+-]+@[\w-]+(\.[\w-]+)+", text)
    put("mentor_email", email.group(0) if email else None, 0.75)
    # Ưu tiên số đứng sau nhãn điện thoại — số 10 chữ số bắt đầu bằng 0 có thể là mã số thuế
    phone = re.search(r"(?:điện\s+thoại|sđt|đt|di\s+động|phone)\s*[:：]?\s*((?:\+84|0)(?:[\s.-]?\d){9,10})", text, re.I)
    if phone:
        put("mentor_phone", phone.group(1), 0.8)
    else:
        tax_digits = re.sub(r"\D", "", tax or "")
        for m in re.finditer(r"(?<!\d)(?:\+84|0)(?:\s?[.-]?\d){9,10}(?!\d)", text):
            if re.sub(r"\D", "", m.group(0)) != tax_digits:
                put("mentor_phone", m.group(0), 0.6)
                break

    period = re.search(rf"từ\s+(?:ngày\s+)?{_DATE}\s+đến\s+(?:ngày\s+)?{_DATE}", text, re.I)
    if period:
        g = period.groups()
        put("start_date", f"{g[0]}/{g[1]}/{g[2]}", 0.85)
        put("end_date", f"{g[3]}/{g[4]}/{g[5]}", 0.85)
    else:
        put("start_date", _labeled(text, r"ngày\s+bắt\s+đầu"), 0.8)
        put("end_date", _labeled(text, r"ngày\s+kết\s+thúc"), 0.8)

    lowered = text.lower()
    if "bán thời gian" in lowered or "part-time" in lowered:
        put("mode", "part_time", 0.8)
    elif "toàn thời gian" in lowered or "full-time" in lowered:
        put("mode", "full_time", 0.8)
    return out


async def llm_extract(text: str) -> ExtractedFields:
    llm = get_llm("classify").with_structured_output(ExtractedFields)
    return await llm.ainvoke(load_prompt("intake_extract.md").replace("{{document}}", text[:12000]))


# ---------------------------------------------------------------- normalize (R2.3)

def normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    m = re.search(_DATE, value)
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
    m = re.search(r"(\d{10})(?:\s*-\s*(\d{3}))?", value)
    if not m:
        return None
    return m.group(1) + (f"-{m.group(2)}" if m.group(2) else "")


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


def build_suggestions(db: Session, extracted: ExtractedFields, source: str) -> dict:
    """Ghép kết quả trích xuất + chuẩn hóa + khớp DN theo mã số thuế."""
    fields: dict[str, dict] = {}
    for name in FIELDS:
        guess: FieldGuess = getattr(extracted, name)
        value = guess.value
        if value is not None and name in _NORMALIZERS:
            value = _NORMALIZERS[name](value)
        if name == "mode" and value not in ("full_time", "part_time"):
            value = None
        if value is None or guess.confidence < MIN_CONFIDENCE:
            fields[name] = {"value": None, "confidence": guess.confidence, "needs_manual": True}
        else:
            fields[name] = {"value": value, "confidence": guess.confidence, "needs_manual": False}

    matched = None
    tax = fields["company_tax_code"]["value"]
    if tax:
        company = db.scalar(select(Company).where(Company.tax_code == tax))
        if company:
            matched = {"id": company.id, "name": company.name}
            fields["company_name"] = {"value": company.name, "confidence": 1.0, "needs_manual": False}
            if company.address:
                fields["company_address"] = {"value": company.address, "confidence": 1.0, "needs_manual": False}
    return {"fields": fields, "matched_company": matched, "source": source, "label": "Gợi ý của AI — hãy kiểm tra trước khi nộp"}


async def extract_suggestions(db: Session, text: str, redactor: Redactor | None = None) -> dict:
    baseline = regex_extract(text)
    if llm_available():
        try:
            guessed = await llm_extract((redactor or Redactor()).redact(text))
            # Trường định danh đã bị che trước khi gửi → luôn lấy từ regex trên bản gốc
            for name in ("company_tax_code", "mentor_email", "mentor_phone"):
                setattr(guessed, name, getattr(baseline, name))
            return build_suggestions(db, guessed, source="llm")
        except Exception:  # LLM lỗi → dùng bộ trích xuất xác định, không chặn SV
            pass
    return build_suggestions(db, baseline, source="rules")
