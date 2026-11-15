# OCR cho giấy tiếp nhận thực tập (scan / ảnh)

## Vấn đề

`/intake/extract` chỉ đọc text layer của PDF, DOCX, TXT. Bản scan (PDF không có text) bị trả 422 "cần nhập tay",
còn ảnh PNG/JPG bị từ chối ngay ở bước kiểm tra định dạng. Giấy nhận thực tập thực tế thường là bản scan/chụp có dấu mộc.

## Đã làm

- **OCR cục bộ bằng Tesseract** (gói `vie` + `eng`), không gọi dịch vụ ngoài → ảnh không rời máy chủ, vẫn chạy khi không có
  `OPENAI_API_KEY`, và văn bản sau OCR vẫn đi qua `Redactor` trước khi tới LLM (NFR-7).
- `src/services/documents.py`: thêm `ocr_image`, `ocr_pdf` (render bằng `pypdfium2` ở 300 DPI, tối đa `OCR_MAX_PAGES` trang),
  `read_document(..., ocr=False)` trả `ExtractedText(text, used_ocr)`. `extract_text` giữ nguyên chữ ký cũ (thêm `ocr=False`).
  OCR **chỉ** chạy khi caller truyền `ocr=True` — upload kho quy định vẫn cần text layer thật.
  PDF có < 30 ký tự text coi là bản scan. Ảnh được xoay theo EXIF và giới hạn 40 triệu pixel.
- `src/api/vin15/internship_routes.py`: `/intake/extract` nhận thêm `.png/.jpg/.jpeg` (tái dùng magic bytes của
  `storage.ALLOWED`), chạy OCR trong threadpool để không chặn event loop. Lỗi thiếu Tesseract / quá thời gian → 422, không 500.
- `src/services/intake.py`: khi từ OCR, mọi độ tin cậy nhân 0.85; response có `"ocr": true`.
- `src/config.py`, `.env.example`: `OCR_ENABLED` (true), `OCR_LANG` (`vie+eng`), `OCR_MAX_PAGES` (3), `OCR_TIMEOUT_SECONDS` (30).
  `OCR_ENABLED=false` quay về hành vi cũ.
- `requirements.txt`: `pytesseract`, `pillow`, `pypdfium2`. `Dockerfile`, `Dockerfile.dev`, CI: cài `tesseract-ocr`, `tesseract-ocr-vie`.
- Frontend `RegistrationForm.jsx`: chọn thêm ảnh, báo "đang đọc…" lâu hơn, nhắc kiểm tra chữ số khi `intake.ocr`.
- PRD lên v0.7 (FR-2.2, §11.4, §12.2, change log).

## Bổ sung: tiến trình xử lý và "thông tin lấy từ đâu"

Phản hồi từ lần dùng thử: bấm "Điền từ file giấy tiếp nhận" không thấy hệ thống đang làm gì, và không biết giá trị gợi ý
nằm ở đâu trong file (nhất là khi OCR đọc sai nên nhiều trường "cần nhập tay").

- **Tiến trình thật qua SSE:** `POST /intake/extract/stream` gửi `stage` theo từng bước (`upload` → `read` → `ocr` trang n/N →
  `extract`) rồi `done` (kèm kết quả) hoặc `error`. Lỗi định dạng/giới hạn tốc độ vẫn trả HTTP 4xx trước khi mở stream.
  `/intake/extract` giữ nguyên, dùng chung `_run_intake`. Frontend: `IntakeProgress.jsx` (stepper, thanh tiến độ theo trang, đếm giây).
- **Vị trí nguồn:** `src/services/documents.py` dựng văn bản OCR từ chính danh sách từ của `image_to_data`, nên offset ký tự khớp
  từng từ; mỗi trang kèm ảnh xem trước (JPEG, base64, **không lưu lên server**) và toạ độ từ chuẩn hoá 0..1.
  `src/services/provenance.py` tìm giá trị thô trong văn bản (bỏ qua khoảng trắng/xuống dòng, ưu tiên khớp đúng hoa/thường) rồi gom
  khung theo dòng. Mỗi trường trả thêm `raw` (đọc được gì) và `source` (`spans`, `boxes`); `document` chứa ảnh trang và văn bản (tối đa 20.000 ký tự).
- **Giao diện:** `IntakeSource.jsx` — tab "Bản gốc" (ảnh + khung sáng, bấm khung để chọn trường) và "Văn bản nhận dạng" (đoạn được tô);
  bảng có cột "Xem trong file". Trường bị loại vì không hợp lệ hiện "đọc được: “…”" để thấy OCR đã đọc sai gì (vd `O1O1234567`).
  File không phải ảnh (DOCX/TXT/PDF có text) chỉ có tab văn bản.
- Giá trị do mô hình AI diễn đạt lại (không có nguyên văn trong file) thì không có `source` — không đoán vị trí.

## Bổ sung: regex trước, LLM chỉ lấp chỗ thiếu, mọi giá trị phải có chỗ để đối chiếu

Trước đây khi có API key, LLM luôn chạy và kết quả của nó thay kết quả regex (trừ MST/email/SĐT), kể cả khi regex đã đúng; giá trị
LLM diễn đạt lại thì không có vùng tô sáng; lỗi LLM bị nuốt im lặng (nên giao diện vẫn ghi "nguồn: theo luật" dù đã có key).

- **Luồng mới** (`extract_suggestions`, `src/services/intake.py`): regex chạy trước trên văn bản gốc. Chỉ khi còn trường cần nhập tay
  **và** có LLM thì mới che PII rồi hỏi LLM, và chỉ hỏi đúng các trường thiếu. MST, email, SĐT không bao giờ hỏi LLM (đã bị che).
  Regex đủ → không có lời gọi LLM nào.
- **Giá trị LLM phải kiểm chứng được** (`merge_llm`): prompt `prompts/intake_extract.md` yêu cầu LLM chép `quote` nguyên văn; hệ thống tìm
  giá trị hoặc `quote` trong file. Tìm thấy → nhận, có vùng tô sáng như giá trị của regex (ngày viết bằng chữ vẫn nhận vì `quote` là chữ gốc).
  Không tìm thấy → loại, trường vẫn "cần nhập tay", giao diện ghi "AI đề xuất “…” nhưng không thấy trong file nên không dùng".
  Trường không được hỏi thì kết quả LLM trả về bị bỏ qua.
- **Mỗi trường có `by`** (`rules` | `llm`), hiện thành nhãn "Theo luật" / "AI" trong bảng. Phản hồi có `llm` = `{available, requested, accepted, error}`;
  `source` là `rules` hoặc `rules+llm`.
- **Lỗi LLM không còn im lặng:** vẫn dùng kết quả regex, nhưng `llm.error` (chỉ tên loại lỗi, không chi tiết nhà cung cấp) làm giao diện
  hiện cảnh báo "Không gọi được mô hình AI … hãy nhập tay phần còn thiếu"; lỗi được ghi log không kèm nội dung.
- `FieldGuess` có thêm `quote` (chỉ LLM điền). `build_suggestions` tách `_finalize_field` dùng chung.

## Bổ sung: cải thiện chất lượng với ảnh chụp điện thoại

Phản hồi từ lần dùng thử: nhiều trường vẫn "cần nhập tay". Chạy Tesseract thật (trong container) trên 5 file mẫu cho thấy scan sạch đọc tốt,
còn **ảnh chụp** chỉ đúng 4/9 trường. Hai nguyên nhân tách biệt: (1) bóng đổ/ánh sáng không đều làm OCR đọc kém; (2) chữ đúng vẫn nằm trong
văn bản nhưng **nhãn bị nhiễu** (mất dấu, mất một phần nhãn, ký tự rác đầu dòng, ngày ngắt dòng) nên regex bỏ sót.

- **Tiền xử lý ảnh** (`src/services/documents.py`): `_enhance` lấy kênh đỏ (mực đỏ của dấu mộc gần như biến mất) và bù bóng đổ bằng cách ước lượng
  nền giấy trên ảnh thu nhỏ; chỉ dùng Pillow. `_ocr_page` OCR bản đã xử lý trước; nếu độ tin cậy trung bình của từ < `OCR_GOOD_CONFIDENCE` (94)
  thì OCR thêm bản xám gốc và lấy bản có độ tin cậy cao hơn (bản xử lý có thể làm hỏng chữ ở vài ảnh scan xám có dấu mộc đè lên).
  Ảnh sạch chỉ tốn một lượt OCR. Thử phóng to / xoay thẳng / đổi `--psm` không cải thiện rõ nên không đưa vào.
- **Bộ trích xuất chịu nhiễu** (`src/services/intake.py`): nhãn khớp trên bản bỏ dấu (`_fold`, giữ nguyên độ dài để vị trí khớp văn bản gốc); chịu ký tự
  rác đầu dòng và nhãn mất một phần ("số thuế", "trí thực tập", "Nguoi hướng dẫn"); MST nhận theo hình dạng dãy 10/13 số khi mất nhãn (tin cậy 0,6 thay vì
  0,9) và `normalize_tax_code` sửa nhầm O/l/S/B → số; ngày chịu ngắt dòng ("05/01⏎/2027") và viết bằng chữ ("5 tháng 1 năm 2027"); tên công ty khi mất nhãn
  nhận theo loại hình (TNHH, Cổ phần…), ưu tiên dòng viết hoa-thường lẫn lộn, bỏ cả câu văn xuôi dài (> 11 từ → để LLM xử lý).
- `scripts/ocr_eval.py`: chạy đúng pipeline trên một thư mục file mẫu và đếm trường đúng
  (`docker compose exec backend python scripts/ocr_eval.py tests/samples/ocr`, thêm `--text` để xem chữ OCR).

Kết quả đo với Tesseract 5.5 (vie+eng) trong container, số trường đúng trên 9 (chỉ phần xác định, chưa tính LLM):

| File mẫu (`tests/samples/ocr`) | Trước | Sau |
|---|---|---|
| 01 scan sạch (PDF / PNG) | 9, 8 | 9, 9 |
| 02 ảnh điện thoại | 4 | 9 |
| 03 scan có dấu mộc | 9 | 9 |
| 04 độ phân giải thấp | 9 | 9 |
| 05 ảnh điện thoại + dấu mộc | 4 | 9 |
| 12 ảnh chụp mới, tham số ngẫu nhiên (chưa dùng để thiết kế) | 104/108 | 108/108 |

Thời gian OCR khoảng 1–3 giây mỗi trang, tới ~5 giây khi phải đọc hai lượt.

## Cách kiểm tra

- `pytest tests/` (cần `pip install -r requirements.txt`): 176 pass, 1 skip (test Tesseract thật, bị bỏ qua khi chưa có binary).
- Test mới: `tests/test_vin15/test_intake_pii.py` (OCR theo cờ, tắt bằng setting, thiếu Tesseract, hạ confidence),
  `tests/test_vin15/test_api_flow.py` (nhận ảnh qua OCR, từ chối ảnh giả, tắt OCR, lỗi OCR → 422) và
  `tests/test_vin15/test_intake_provenance.py` (offset từ khớp văn bản, toạ độ khung, giá trị trải nhiều dòng, SĐT có dấu cách,
  hình thức làm việc, `raw` cho trường không hợp lệ, trình tự sự kiện SSE, lỗi tường minh) cùng luồng LLM lấp chỗ thiếu (regex đủ thì không gọi LLM,
  chỉ hỏi đúng trường thiếu trên văn bản đã che, nhận giá trị có `quote` trong file, loại giá trị bịa, bỏ qua trường không hỏi,
  lỗi LLM giữ kết quả regex và không lộ chi tiết, chỉ thiếu MST/email/SĐT thì không gọi).
- `tests/test_vin15/test_intake_robust.py`: dùng **hai đoạn chữ OCR thật** của ảnh chụp làm test hồi quy, cùng test riêng cho từng kiểu nhiễu (ký tự rác, nhãn mất dấu,
  MST không nhãn và nhầm O/0, ngày ngắt dòng, ngày bằng chữ, tên công ty theo loại hình). `test_intake_provenance.py` thêm test `_enhance` (nền về trắng đều, dấu đỏ nhạt đi)
  và `_ocr_page` (giữ bản đầu khi đủ tin cậy, chọn bản tốt hơn khi chưa chắc).
- Kiểm tra giao diện bằng Chrome headless: chạy API thật nhưng thay riêng lời gọi Tesseract bằng từ giả lập theo bố cục file mẫu,
  chụp màn hình tiến trình, bảng, khung xem nguồn, tab văn bản — không lỗi JS, khung bám đúng chữ. Script nằm ngoài repo, không commit.
- `ruff check src/ tests/` sạch; `npm run build` trong `frontend/` thành công.
- Thủ công: `docker build -f Dockerfile.dev`, chạy pytest để bật test Tesseract thật; đăng nhập `sv01`, upload scan ở "Điền từ file giấy tiếp nhận".

## Mức hiện tại và tiêu chí đạt

Đo nghiêm ngặt (so từng ký tự, kể cả dấu) trên 18 ảnh giả lập (6 mẫu + 12 ảnh chụp mới): **15/18 file đúng toàn bộ 10 trường**; 3 file còn lại mỗi file sai
đúng một ký tự ở trường văn bản tự do (địa chỉ `Ha Nội` / `Cầu Giầy`, mô tả `AP|` thay `API`). MST, ngày, email, SĐT đúng cả 18/18.
Lưu ý `scripts/ocr_eval.py` **bỏ dấu khi so** tên công ty, địa chỉ, người hướng dẫn (để chịu lỗi OCR nhỏ), nên con số của nó ("9/9") lạc quan hơn đo nghiêm ngặt.

Đánh giá: **nhận được cho demo / thử nghiệm nhỏ, chưa đủ bằng chứng cho dùng thật.** Lý do nhận được: gợi ý không tự ghi vào hồ sơ, có khung tô sáng để đối chiếu,
trường không chắc thì để "cần nhập tay", và còn kiểm tra theo quy chế + giảng viên duyệt phía sau. Lý do chưa đủ: mọi số liệu là ảnh giả lập; chưa xử lý méo phối cảnh,
giấy nhăn/cong, ánh đèn chói, chữ viết tay; rủi ro lớn nhất là sinh viên bấm "Điền vào form" mà không kiểm tra.

Tiêu chí đề xuất để coi là đạt cho dùng thật (cần chốt với người phụ trách):
1. Thử trên khoảng 20 ảnh/scan thật (đã che thông tin cá nhân), gồm cả ca xấu.
2. Các trường định danh (MST, ngày bắt đầu, ngày kết thúc) đúng ≥ 90% số file; trường văn bản tự do sai thì chấp nhận vì đã có bước người dùng kiểm tra.
3. Không có trường nào sai mà vẫn hiện độ tin cậy cao và không có cảnh báo.

## Chưa kiểm tra / lưu ý

- **Chưa có ảnh/scan thật nào của sinh viên.** Số liệu ở trên là ảnh giả lập từ cùng một trình sinh; hai file 02 và 05 được dùng để thiết kế nên con số của chúng lạc quan,
  bộ 12 ảnh mới dễ hơn (code cũ đã đúng 96%). Cần thử và bổ sung vào bộ mẫu rồi chạy lại `scripts/ocr_eval.py` (sửa `CHECKS` cho khớp thư đó).
- Chưa xử lý: méo phối cảnh (chụp lệch góc), giấy nhăn/cong, ánh đèn chói, chữ viết tay, bố cục nhiều cột/bảng. Sửa nhầm chữ số O/l/S/B chỉ áp dụng cho mã số thuế,
  chưa cho ngày và SĐT (`05/O1/2027` vẫn thành "cần nhập tay").
- "Sửa nhầm O/l/S/B → số" cho mã số thuế coi mọi dãy 10 ký tự toàn thuộc nhóm đó (có ≥ 7 chữ số thật) là mã số thuế; MST nhận theo hình dạng (mất nhãn) có thể nhầm
  một số điện thoại viết liền ở dòng không có nhãn (đã trừ dòng có nhãn điện thoại) — vì vậy chỉ tin cậy 0,6 và vẫn có khung tô sáng để người dùng kiểm tra.
- Chưa làm: tô màu từ OCR có độ tin cậy thấp, thử `tessdata_best` hoặc engine OCR khác (chưa cần trước khi có ảnh thật).
- Toạ độ khung tô sáng đã kiểm tra trên giao diện với từ **giả lập**; chưa xem trên giao diện với đầu ra Tesseract thật (chữ OCR thật đã được dùng cho test trích xuất).
  Ảnh chụp nghiêng/có dấu mộc có thể cho khung lệch nhẹ nếu Tesseract tách từ khác.
- **Chưa gọi LLM thật** với prompt mới (chỉ hàm giả lập): chưa biết model có chép `quote` nguyên văn đủ ổn định không, nhất là trên văn bản OCR có lỗi chữ.
  Nếu `quote` hay sai thì nhiều giá trị AI sẽ bị loại. Cần thử với key thật trên thư văn xuôi; nếu giao diện hiện cảnh báo "Không gọi được mô hình AI" thì kiểm tra key.
- Ảnh trang gửi kèm phản hồi (khoảng vài trăm KB mỗi trang, tối đa 3 trang); chưa đo trên mạng chậm.
- Chưa có test tự động cho giao diện React (vẫn là khoảng trống đã ghi trong PRD §11.4).
- Image Docker đã build và chạy (Tesseract 5.5.0 + gói `vie`), nhưng chưa đo dung lượng tăng thêm.
- OCR chạy CPU trong cùng process với API; nhiều người upload cùng lúc sẽ chiếm CPU. Hiện chỉ giảm nhẹ bằng threadpool và rate limit.
- OCR có thể nhầm chữ số; vẫn dựa vào bước sinh viên xác nhận và bước `validate` theo quy chế.
