"""Sinh file mẫu GIẢ LẬP để thử OCR giấy tiếp nhận thực tập (/intake/extract).

Dữ liệu hoàn toàn tổng hợp (công ty khớp danh mục seed, mã số thuế 0101234567), không có thông tin thật.
Chạy:  python scripts/make_ocr_samples.py [thư_mục_đầu_ra]   (mặc định tests/samples/ocr)
Cần: pillow. Font: Arial (Windows), hoặc DejaVu/Liberation (Linux) — phải hỗ trợ tiếng Việt.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

DPI = 300
A4 = (int(8.27 * DPI), int(11.69 * DPI))  # 2481 x 3507
FONT_DIRS = ("C:/Windows/Fonts", "/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation")
REGULAR = ("arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf")
BOLD = ("arialbd.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf")

# Giá trị mong đợi sau khi trích xuất — ghi vào README cạnh các file mẫu
EXPECTED = {
    "company_name": "Công ty TNHH Giải pháp Phần mềm Sao Mai",
    "company_tax_code": "0101234567",
    "start_date": "2027-01-05",
    "end_date": "2027-03-30",
    "mentor_email": "bao.tq@saomai.vn",
    "mentor_phone": "0912345678",
    "mode": "full_time",
}

LETTER = [
    ("CÔNG TY TNHH GIẢI PHÁP PHẦN MỀM SAO MAI", "title"),
    ("Số: 15/2026/SM-TN", "small"),
    ("", None),
    ("GIẤY XÁC NHẬN TIẾP NHẬN THỰC TẬP", "title"),
    ("", None),
    ("Kính gửi: Khoa Công nghệ thông tin, Trường Đại học VinUni", "body"),
    ("", None),
    ("Công ty chúng tôi xác nhận tiếp nhận sinh viên thực tập với các thông tin sau:", "body"),
    ("", None),
    ("Tên công ty: Công ty TNHH Giải pháp Phần mềm Sao Mai", "body"),
    ("Mã số thuế: 0101234567", "body"),
    ("Địa chỉ: 12 Duy Tân, Cầu Giấy, Hà Nội", "body"),
    ("Vị trí thực tập: Thực tập sinh Backend", "body"),
    ("Mô tả công việc: Phát triển API và viết kiểm thử tự động", "body"),
    ("Người hướng dẫn: Ông Trần Quốc Bảo", "body"),
    ("Email liên hệ: bao.tq@saomai.vn", "body"),
    ("Điện thoại: 0912 345 678", "body"),
    ("Thời gian: từ ngày 05/01/2027 đến ngày 30/03/2027, toàn thời gian.", "body"),
    ("", None),
    ("Hà Nội, ngày 20 tháng 11 năm 2026", "right"),
    ("ĐẠI DIỆN CÔNG TY", "right"),
    ("(Ký, ghi rõ họ tên)", "right"),
]


def _font(names: tuple[str, ...], size: int) -> ImageFont.FreeTypeFont:
    for folder in FONT_DIRS:
        for name in names:
            path = Path(folder) / name
            if path.exists():
                return ImageFont.truetype(str(path), size)
    raise SystemExit("Không tìm thấy font hỗ trợ tiếng Việt (Arial/DejaVu/Liberation)")


def render_letter() -> tuple[Image.Image, dict[str, tuple[int, int]]]:
    """Vẽ thư lên khổ A4 300 DPI; trả ảnh và toạ độ một số dòng để đặt dấu mộc."""
    img = Image.new("RGB", A4, "white")
    draw = ImageDraw.Draw(img)
    sizes = {"title": (BOLD, 58), "body": (REGULAR, 46), "small": (REGULAR, 38), "right": (REGULAR, 46)}
    fonts = {k: _font(*v) for k, v in sizes.items()}
    margin, y = 230, 260
    anchors: dict[str, tuple[int, int]] = {}
    for text, kind in LETTER:
        if kind is None:
            y += 55
            continue
        font = fonts[kind]
        width = draw.textlength(text, font=font)
        x = (A4[0] - width) / 2 if kind == "title" else (A4[0] - margin - width if kind == "right" else margin)
        draw.text((x, y), text, fill=(15, 15, 15), font=font)
        if text.startswith("Thời gian"):
            anchors["period_end"] = (int(x + width), y)
        if text.startswith("ĐẠI DIỆN"):
            anchors["signature"] = (int(x + width / 2), y)
        y += int(font.size * 1.55)
    return img, anchors


def add_stamp(img: Image.Image, center: tuple[int, int], radius: int = 230) -> Image.Image:
    """Dấu mộc đỏ bán trong suốt, đè lên chữ như dấu thật."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    red = (200, 30, 40, 170)
    cx, cy = center
    d.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=red, width=10)
    d.ellipse((cx - radius + 40, cy - radius + 40, cx + radius - 40, cy + radius - 40), outline=red, width=4)
    f = _font(BOLD, 34)
    for i, line in enumerate(("CÔNG TY TNHH", "GIẢI PHÁP PHẦN MỀM", "SAO MAI", "* * *", "HÀ NỘI")):
        w = d.textlength(line, font=f)
        d.text((cx - w / 2, cy - 105 + i * 50), line, fill=red, font=f)
    layer = layer.rotate(-12, center=center, resample=Image.BICUBIC)
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def scan_effect(img: Image.Image, seed: int = 1) -> Image.Image:
    """Máy scan: xám nhẹ, nhiễu hạt, hơi mờ."""
    random.seed(seed)
    g = img.convert("L").filter(ImageFilter.GaussianBlur(0.8))
    noise = Image.effect_noise(g.size, 10)
    return ImageChops.add(g, noise, scale=1, offset=-128)


def phone_photo(img: Image.Image, seed: int = 2) -> Image.Image:
    """Ảnh chụp điện thoại: nghiêng, bóng đổ chéo, nhiễu, mờ, giảm độ phân giải."""
    random.seed(seed)
    tilted = img.convert("RGB").rotate(2.5, expand=True, fillcolor=(205, 195, 180), resample=Image.BICUBIC)
    # Bóng đổ chéo mượt: trộn gradient dọc và ngang (xoay gradient sẽ để lại góc đen, mảng cứng)
    vertical = Image.linear_gradient("L").resize(tilted.size)
    horizontal = vertical.transpose(Image.ROTATE_90).resize(tilted.size)
    shade = Image.blend(vertical, horizontal, 0.5).point(lambda v: 180 + v * 75 // 255).convert("RGB")  # 0.7 .. 1.0
    out = ImageChops.multiply(tilted, shade).filter(ImageFilter.GaussianBlur(1.6))
    noise = Image.effect_noise(out.size, 16).convert("RGB")
    out = ImageChops.add(out, noise, scale=1, offset=-128)
    return out.resize((1700, int(1700 * out.height / out.width)), Image.LANCZOS)


def main(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    base, anchors = render_letter()

    # 1. Scan sạch → PDF chỉ chứa ảnh (không có text layer) + PNG
    clean = scan_effect(base)
    clean.save(out_dir / "01-scan-sach.pdf", resolution=DPI)
    clean.save(out_dir / "01-scan-sach.png")

    # 2. Ảnh chụp điện thoại (JPG)
    phone_photo(base).save(out_dir / "02-anh-dien-thoai.jpg", quality=72)

    # 3. Có dấu mộc đè lên cuối dòng "Thời gian" và khối chữ ký → scan
    stamped = add_stamp(base, (anchors["period_end"][0] - 60, anchors["period_end"][1] + 40), radius=210)
    stamped = add_stamp(stamped, (anchors["signature"][0], anchors["signature"][1] + 170))
    scan_effect(stamped, seed=3).save(out_dir / "03-dau-moc-de-chu.pdf", resolution=DPI)

    # 4. Độ phân giải thấp (~100 DPI) — trường hợp xấu
    low = scan_effect(base).resize((A4[0] // 3, A4[1] // 3), Image.LANCZOS)
    low.save(out_dir / "04-do-phan-giai-thap.jpg", quality=60)

    # 5. Ảnh chụp + dấu mộc (khó nhất)
    phone_photo(stamped, seed=4).save(out_dir / "05-anh-dien-thoai-co-moc.jpg", quality=70)

    expected = "\n".join(f"- `{k}`: {v}" for k, v in EXPECTED.items())
    (out_dir / "README.md").write_text(
        "# File mẫu thử OCR (dữ liệu giả lập)\n\n"
        "Sinh bằng `python scripts/make_ocr_samples.py`. Không chứa thông tin thật.\n\n"
        "| File | Mô phỏng |\n|---|---|\n"
        "| `01-scan-sach.pdf` / `.png` | Scan sạch 300 DPI (PDF chỉ có ảnh, không có text layer) |\n"
        "| `02-anh-dien-thoai.jpg` | Ảnh chụp điện thoại: nghiêng, bóng đổ, nhiễu |\n"
        "| `03-dau-moc-de-chu.pdf` | Scan có dấu mộc đỏ đè lên chữ |\n"
        "| `04-do-phan-giai-thap.jpg` | Độ phân giải thấp (~100 DPI) |\n"
        "| `05-anh-dien-thoai-co-moc.jpg` | Ảnh chụp + dấu mộc (khó nhất) |\n\n"
        f"## Giá trị đúng cần trích ra\n\n{expected}\n\n"
        "Công ty khớp danh mục seed theo mã số thuế nên tên/địa chỉ được lấy từ danh mục.\n"
        "Đăng nhập `sv01` / `demo123`, chọn \"Điền từ file giấy tiếp nhận\" và so sánh.\n",
        encoding="utf-8",
    )
    print(f"Đã tạo {len(list(out_dir.iterdir()))} file trong {out_dir}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tests/samples/ocr"))
