"""Intake Extractor (R2.2–2.3), storage (R5.2), PII redactor (R15.2)."""

from __future__ import annotations

import io

import pytest

from src.services import intake
from src.services.documents import extract_text
from src.services.pii import Redactor
from src.services.storage import FileRejected, check_file

LETTER = """GIẤY XÁC NHẬN TIẾP NHẬN THỰC TẬP
Tên công ty: Cty TNHH Giải pháp Phần mềm Sao Mai
Mã số thuế: 0101234567
Địa chỉ: 12 Duy Tân, Cầu Giấy, Hà Nội
Vị trí thực tập: Thực tập sinh Backend
Mô tả công việc: Phát triển API và viết kiểm thử tự động
Người hướng dẫn: Ông Trần Quốc Bảo
Email liên hệ bao.tq@saomai.vn, điện thoại 0912 345 678
Thời gian: từ ngày 05/01/2027 đến ngày 30/03/2027, toàn thời gian.
"""


def test_regex_extract_and_normalize(db):
    result = intake.build_suggestions(db, intake.regex_extract(LETTER), source="rules")
    f = {k: v["value"] for k, v in result["fields"].items()}
    assert f["company_tax_code"] == "0101234567"
    assert f["start_date"] == "2027-01-05" and f["end_date"] == "2027-03-30"
    assert f["mentor_email"] == "bao.tq@saomai.vn"
    assert f["mentor_phone"] == "0912345678"
    assert f["mode"] == "full_time"
    assert f["position"] == "Thực tập sinh Backend"
    # khớp DN đã có theo mã số thuế → dùng tên chuẩn trong danh mục
    assert result["matched_company"]["name"] == "Công ty TNHH Giải pháp Phần mềm Sao Mai"
    assert f["company_name"] == "Công ty TNHH Giải pháp Phần mềm Sao Mai"


def test_missing_fields_are_marked_manual(db):
    result = intake.build_suggestions(db, intake.regex_extract("Thư mời thực tập.\nVị trí: Kế toán"), source="rules")
    assert result["fields"]["company_tax_code"] == {"value": None, "confidence": 0.0, "needs_manual": True}
    assert result["fields"]["position"]["value"] == "Kế toán"


@pytest.mark.parametrize("raw,expected", [
    ("31/02/2027", None), ("2027-01-05", "2027-01-05"), ("5.1.2027", "2027-01-05"),
])
def test_normalize_date(raw, expected):
    assert intake.normalize_date(raw) == expected


def test_docx_parsing_roundtrip():
    from docx import Document

    doc = Document()
    for line in LETTER.splitlines():
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    text = extract_text("giay.docx", buf.getvalue())
    assert "Mã số thuế: 0101234567" in text


def test_storage_rejects_spoofed_and_oversized_files(monkeypatch):
    from src.config import get_settings

    with pytest.raises(FileRejected):
        check_file("virus.exe", b"MZ...")
    with pytest.raises(FileRejected):
        check_file("fake.pdf", b"not a pdf")
    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)
    with pytest.raises(FileRejected):
        check_file("big.pdf", b"%PDF" + b"0" * (1024 * 1024 + 1))
    assert check_file("ok.pdf", b"%PDF-1.4") == "application/pdf"


def test_redactor_masks_known_and_pattern_pii():
    r = Redactor({"HO_TEN": "Lê Thị Chi", "MSSV": "SV2026003"})
    out = r.redact("Em là lê thị chi (SV2026003), mail chi@x.vn, sđt +84 912 345 678, MST 0101234567")
    assert r.leaked(out) == []
    for token in ("<HO_TEN>", "<MSSV>", "<EMAIL>", "<SDT>"):
        assert token in out
    # MST 10 số bắt đầu bằng 0 trùng dạng SĐT — nhãn có thể khác, nhưng giá trị phải bị che
    assert "0101234567" not in out and "912 345 678" not in out
    assert "<SO_ID>" in r.redact("CCCD 001203004567")
