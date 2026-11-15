"""Đo chất lượng đọc giấy tiếp nhận: chạy đúng pipeline của ứng dụng (đọc file/OCR → bộ trích xuất regex) trên một thư mục
file mẫu rồi đếm số trường đúng. Chỉ đo phần xác định (chưa tính LLM). Giá trị đúng là của thư mà
`scripts/make_ocr_samples.py` sinh ra — nếu dùng thư thật thì sửa CHECKS cho khớp.

Dùng:  python scripts/ocr_eval.py [thư_mục=tests/samples/ocr] [--text]
Docker: docker compose exec backend python scripts/ocr_eval.py tests/samples/ocr
  --text  in cả văn bản OCR của từng file (để xem Tesseract thật sự đọc ra gì)
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.services import documents, intake  # noqa: E402

fold = intake._fold  # noqa: SLF001

CHECKS = {
    "company_name": lambda v: "sao mai" in fold(v or ""),
    "company_tax_code": lambda v: intake.normalize_tax_code(v) == "0101234567",
    "company_address": lambda v: "duy tan" in fold(v or ""),
    "position": lambda v: "backend" in (v or "").lower(),
    "start_date": lambda v: intake.normalize_date(v) == "2027-01-05",
    "end_date": lambda v: intake.normalize_date(v) == "2027-03-30",
    "mentor_name": lambda v: "bao" in fold(v or ""),
    "mentor_email": lambda v: intake.normalize_email(v) == "bao.tq@saomai.vn",
    "mentor_phone": lambda v: intake.normalize_phone(v) == "0912345678",
}
EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".docx", ".txt"}


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    folder = Path(args[0]) if args else ROOT / "tests" / "samples" / "ocr"
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in EXTS)
    if not files:
        raise SystemExit(f"Không có file mẫu trong {folder}")
    total = correct = 0
    for path in files:
        started = time.time()
        try:
            doc = documents.read_document(path.name, path.read_bytes(), ocr=True)
        except documents.UnreadableDocument as exc:
            print(f"{path.name}: KHÔNG ĐỌC ĐƯỢC — {exc}")
            total += len(CHECKS)
            continue
        extracted = intake.regex_extract(doc.text)
        wrong = [name for name, ok in CHECKS.items() if not ok(getattr(extracted, name).value)]
        total += len(CHECKS)
        correct += len(CHECKS) - len(wrong)
        print(f"{path.name}: {len(CHECKS) - len(wrong)}/{len(CHECKS)} trường đúng · {time.time() - started:.1f}s"
              f"{' · OCR' if doc.used_ocr else ''}{' · sai: ' + ', '.join(wrong) if wrong else ''}")
        if "--text" in sys.argv:
            print(doc.text)
    print(f"TỔNG: {correct}/{total} trường đúng trên {len(files)} file ({100 * correct / total:.0f}%)")


if __name__ == "__main__":
    main()
