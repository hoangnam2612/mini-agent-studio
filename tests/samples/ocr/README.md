# File mẫu thử OCR (dữ liệu giả lập)

Sinh bằng `python scripts/make_ocr_samples.py`. Không chứa thông tin thật.

| File | Mô phỏng |
|---|---|
| `01-scan-sach.pdf` / `.png` | Scan sạch 300 DPI (PDF chỉ có ảnh, không có text layer) |
| `02-anh-dien-thoai.jpg` | Ảnh chụp điện thoại: nghiêng, bóng đổ, nhiễu |
| `03-dau-moc-de-chu.pdf` | Scan có dấu mộc đỏ đè lên chữ |
| `04-do-phan-giai-thap.jpg` | Độ phân giải thấp (~100 DPI) |
| `05-anh-dien-thoai-co-moc.jpg` | Ảnh chụp + dấu mộc (khó nhất) |

## Giá trị đúng cần trích ra

- `company_name`: Công ty TNHH Giải pháp Phần mềm Sao Mai
- `company_tax_code`: 0101234567
- `start_date`: 2027-01-05
- `end_date`: 2027-03-30
- `mentor_email`: bao.tq@saomai.vn
- `mentor_phone`: 0912345678
- `mode`: full_time

Công ty khớp danh mục seed theo mã số thuế nên tên/địa chỉ được lấy từ danh mục.
Đăng nhập `sv01` / `demo123`, chọn "Điền từ file giấy tiếp nhận" và so sánh.
