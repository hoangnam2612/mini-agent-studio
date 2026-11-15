"""Bộ trích xuất chịu được nhiễu OCR. Hai đoạn OCR bên dưới là đầu ra THẬT của Tesseract 5.5 (vie+eng) trên ảnh chụp
điện thoại giả lập trong tests/samples/ocr (dữ liệu tổng hợp, không có thông tin thật); trước khi chịu nhiễu thì chỉ
đúng 4/9 trường."""

from __future__ import annotations

from src.services import intake
from src.services.documents import ExtractedText
from src.services.provenance import locate

OCR_PHONE_PHOTO = """PHAP PHAN MEM SAO MAI
GIAY XÁC NHAN TIẾP NHAN THỰC TAP
Công nghệ hông tin, Trường Đi học VU
chúng wen lắp nhận nhiên thực tập với ác thông tn sa
Tên công | - Công ty TNHH Giải pháp Phần mém Sao Mai
:0101234567 -
Địa chỉ: 12 Duy Tân, Cầu Giấy, Hà Nội
Vị trí thực tập: Thực tập sinh Backend
Mô tả công việc: Phát triển API và viết kiểm thử tự động
' Người hướng dẫn: Ông Tran Quốc Bảo
: mail liên hệ: bao.tq@saomai.vn
_ Điện thoại: 0912 345 678
: Thời gian: từ ngày 05/01
/2027 đến ngày 30/03/2027, toàn thời gian.
Hà Nội, ngày 20 tháng 11 năm 2026
ĐẠI DIEN CÔNG TY
(Ký, ghi rõ họ tên)
"""

OCR_PHONE_PHOTO_STAMP = """Khoa Công nghệ thông ¡Dạ bọc vont
0isác hận tấp nhện in dân tực vi ác on
số thuế: (0101234567
Địa chỉ: 12 Duy Tan, Cầu Giấy, Hà Nội
/\\ trí thực tập: Thực tập sinh Backend
__ Mô tả công việc: Phát triển API và viết kiểm thử tự động
Nguoi hướng dẫn: Ông Tràn Quốc Bảo
_ Email liên hệ: bao.tq@saomai.vn
_ Điện thoại: 0912 345 678
__ Thời gian: từ ngày 05/01/2027 đến ngày 30/03/2027,
"""


def _raw(text: str) -> dict:
    ex = intake.regex_extract(text)
    return {name: getattr(ex, name).value for name in intake.FIELDS}


def test_real_ocr_of_phone_photo_is_fully_extracted(db):
    raw = _raw(OCR_PHONE_PHOTO)
    assert raw["company_name"] == "Công ty TNHH Giải pháp Phần mém Sao Mai"  # nhãn mất "ty": nhận theo loại hình công ty
    assert raw["company_tax_code"] == "0101234567"  # mất hẳn nhãn "Mã số thuế"
    assert raw["mentor_name"] == "Ông Tran Quốc Bảo"  # ký tự rác "' " đầu dòng
    assert raw["mentor_phone"] == "0912 345 678" and raw["mentor_email"] == "bao.tq@saomai.vn"
    assert raw["company_address"] == "12 Duy Tân, Cầu Giấy, Hà Nội" and raw["position"] == "Thực tập sinh Backend"
    assert raw["mode"] == "full_time"
    # ngày bị ngắt dòng giữa chừng vẫn đọc được, và tô sáng được đúng chỗ trong file
    fields = intake.build_suggestions(db, intake.regex_extract(OCR_PHONE_PHOTO), source="rules")["fields"]
    assert fields["start_date"]["value"] == "2027-01-05" and fields["end_date"]["value"] == "2027-03-30"
    src = locate(ExtractedText(OCR_PHONE_PHOTO), "start_date", raw["start_date"])
    start, end = src["spans"][0]
    assert OCR_PHONE_PHOTO[start:end] == "05/01\n/2027"
    assert all(not f["needs_manual"] for f in fields.values())


def test_real_ocr_of_stamped_phone_photo(db):
    raw = _raw(OCR_PHONE_PHOTO_STAMP)
    assert raw["company_tax_code"] == "0101234567"  # nhãn mất chữ "Mã", giá trị có "(" dính vào
    assert raw["position"] == "Thực tập sinh Backend"  # nhãn "/\\ trí thực tập" mất chữ "Vị"
    assert raw["mentor_name"] == "Ông Tràn Quốc Bảo"  # "Nguoi" mất dấu
    assert raw["company_address"] == "12 Duy Tan, Cầu Giấy, Hà Nội"
    assert raw["start_date"] == "05/01/2027" and raw["end_date"] == "30/03/2027"
    # dòng tên công ty bị OCR làm hỏng hoàn toàn → regex không đoán, để LLM hoặc người dùng
    assert raw["company_name"] is None and raw["mode"] is None


def test_labels_tolerate_junk_prefix_and_missing_diacritics():
    raw = _raw("' Người hướng dẫn: Ông A\n__ Mô tả công viec: Viet API\nDia chi: 1 Phố Huế\n| Vị trí: Kế toán\n")
    assert raw["mentor_name"] == "Ông A" and raw["job_description"] == "Viet API"
    assert raw["company_address"] == "1 Phố Huế" and raw["position"] == "Kế toán"
    # giá trị phải cùng dòng với nhãn: nhãn bỏ trống không được nuốt dòng kế tiếp
    assert _raw("Mô tả công việc:\nNgười hướng dẫn: Ông B\n")["job_description"] is None


def test_tax_code_by_shape_and_digit_confusion():
    ex = intake.regex_extract("Nơi thực tập: X\n:0101234567 -\n")
    assert ex.company_tax_code.value == "0101234567" and ex.company_tax_code.confidence == 0.6  # không nhãn → tin cậy thấp hơn
    ex = intake.regex_extract("Mã số thuế: O1O1234567\n")  # chữ O đọc nhầm số 0
    assert ex.company_tax_code.value == "O1O1234567" and ex.company_tax_code.confidence == 0.9
    assert intake.normalize_tax_code("O1O1234567") == "0101234567"
    assert intake.normalize_tax_code("0101234567 - 001") == "0101234567-001"
    assert intake.normalize_tax_code("SBOBOBOBOB") is None  # toàn chữ → không phải số
    # số điện thoại viết liền trên dòng điện thoại không bị nhận làm mã số thuế
    ex = intake.regex_extract("Điện thoại: 0912345678\n0101234567\n")
    assert ex.company_tax_code.value == "0101234567" and ex.mentor_phone.value == "0912345678"
    assert intake.regex_extract("Điện thoại: 0912345678\n").company_tax_code.value is None


def test_dates_across_linebreak_and_written_in_words():
    ex = intake.regex_extract("Thực tập từ ngày 5 tháng 1 năm 2027 đến ngày 30 tháng 3 năm 2027.")
    assert intake.normalize_date(ex.start_date.value) == "2027-01-05" and intake.normalize_date(ex.end_date.value) == "2027-03-30"
    ex = intake.regex_extract("từ ngày 05/01\n/2027 đến ngày 30/03\n/2027")
    assert intake.normalize_date(ex.start_date.value) == "2027-01-05" and intake.normalize_date(ex.end_date.value) == "2027-03-30"
    assert intake.normalize_date("5 tháng 1 năm 2027") == "2027-01-05" and intake.normalize_date("31/02/2027") is None


def test_company_name_by_legal_form_ignores_sentences_and_prefers_mixed_case():
    title = "CÔNG TY TNHH SAO MAI\n"
    assert intake.regex_extract(title).company_name.confidence == 0.6  # chỉ có tiêu đề IN HOA
    both = intake.regex_extract(title + "Tên công | - Công ty TNHH Sao Mai\n")
    assert both.company_name.value == "Công ty TNHH Sao Mai" and both.company_name.confidence == 0.7
    sentence = "Công ty Cổ phần Ánh Dương trân trọng thông báo tiếp nhận sinh viên thực tập tại đơn vị.\n"
    assert intake.regex_extract(sentence).company_name.value is None  # cả câu, không phải tên
    assert intake.regex_extract("Công ty chúng tôi xác nhận tiếp nhận sinh viên.\n").company_name.value is None
