# Wireframe cổng thực tập (low-fi, HTML in được)

## 1. Mục tiêu

Có bộ wireframe để nộp cùng PRD: vẽ lại 14 màn của frontend React hiện tại (main `c3e71ab`), mỗi màn có bản
desktop và mobile, chú thích trỏ về mã yêu cầu trong `PRD.md`. Xuất được PDF hoặc từng màn.

## 2. Đã làm

| File | Nội dung |
|---|---|
| `docs/wireframe/vin15-wireframe.html` | Nguồn wireframe (cũng là bản publish artifact). JS dựng các tờ từ mô tả màn trong mảng `SCREENS`. |
| `docs/wireframe/export.mjs` | Tạo bản in, PDF và PNG bằng Chrome headless (dùng `puppeteer-core` của `tests/ui`). |
| `docs/wireframe/export/vin15-wireframe-print.html` | Bản có `<!doctype>` để mở trực tiếp và in (sinh ra từ nguồn, đừng sửa tay). |
| `docs/wireframe/export/vin15-wireframe.pdf` | 16 tờ A4 ngang: bìa, sơ đồ, S01–S14. |
| `docs/wireframe/export/png/*.png` | Mỗi tờ một ảnh (2x), tên theo mã màn. |

Artifact (riêng tư, chủ tài khoản mở được cho tới khi chia sẻ): https://claude.ai/artifact/F1svaYeyv441RXPmMm1ZtB

**Quy ước wireframe đã theo:**
- **Low-fi, thang xám thuần.** Không dùng màu thương hiệu; chỉ chú thích dùng một màu đỏ (redline).
- **Nhãn chữ là nhãn thật của giao diện.** Đoạn văn dài thay bằng thanh xám; ảnh, avatar, logo thay bằng ô có dấu X.
- **Ký hiệu riêng.** Ô do AI điền dùng viền đứt + gạch chéo + nhãn "AI điền"; nội dung AI sinh nằm trong khung đứt, gạch chéo. Nút chính tô đậm, nút phụ chỉ có viền, nút từ chối viền đứt.
- **Mỗi màn một tờ A4 ngang**, gồm:
  - Khung tên: mã, tên, mục đích, vai trò, route, phiên bản, ngày, viewport.
  - Desktop 1440 px và mobile 390 px đặt cạnh nhau.
  - Cột chú thích đánh số khớp chấm đỏ, kèm mã FR.
  - Dòng "Trạng thái khác" cho các trạng thái trống, lỗi, chặn.
- **Tờ đầu là bìa và sơ đồ.** Bìa có ký hiệu, mục lục màn và cách xuất. Tờ sơ đồ có sitemap theo vai trò và luồng chính dạng làn (đánh dấu bước HITL và bước do AI hoặc tác tử thực hiện).
- **Cùng một nội dung cho hai khổ.** CSS container query đổi bố cục khi khung hẹp, nên desktop và mobile không lệch nhau.
- **Khung desktop tự co nội dung** (tối thiểu 58%) để hiện đủ trang; chú thích không trỏ vào phần bị khuất. Khung mobile chỉ co tới 80%, màn dài ghi "trang còn tiếp khi cuộn".

## 3. File HTML từng màn để import vào Figma

`docs/wireframe/figma/` (nén sẵn: `docs/wireframe/vin15-wireframe-figma.zip`) — 28 file HTML tĩnh, mỗi file **chỉ có màn hình**:
không khung tên, không chú thích, không chấm đỏ, không khung thiết bị, không JavaScript.

- `figma/desktop/Sxx-<tên>.html`: khổ 1440 px (chữ cơ sở 16 px), cao tối thiểu 900 px, dài theo nội dung.
- `figma/mobile/Sxx-<tên>.html`: khổ 390 px (chữ cơ sở 14 px), cao tối thiểu 844 px.
- Bố cục đóng cứng cho từng khổ (không dùng container query) vì plugin import thường chỉ đọc CSS tĩnh.
- Font Be Vietnam Pro (Google Fonts, có sẵn trong Figma).

Import: Figma → plugin **html.to.design** → tải file HTML lên (hoặc kéo thả), mỗi file thành một frame.
Tạo lại: `node docs/wireframe/export-figma.mjs` (đọc mảng `SCREENS` trong file nguồn, chụp kiểm tra vào `export/figma-check/` với JS tắt).

## 4. Cách xuất lại

```bash
cd tests/ui && npm i            # một lần, lấy puppeteer-core
cd ../.. && node docs/wireframe/export.mjs
```

In tay: mở `docs/wireframe/export/vin15-wireframe-print.html` trong Chrome hoặc Edge → Ctrl+P → A4, ngang, tắt đầu trang/chân trang, bật đồ họa nền.
Một màn: thêm `#S04` (mã màn) vào cuối địa chỉ rồi in. Trong artifact, bấm mã trên thanh công cụ để xem riêng từng màn.

## 5. Đã kiểm tra

- Xuất đủ 16 tờ PDF và 16 PNG. Tất cả khung desktop hiện đủ nội dung. S07 không vẽ nút "Lập chỉ mục lại" vì giao diện chưa có (chỉ có API).
- Năm màn mobile dài (S03, S04, S07, S08, S12) có ghi "trang còn tiếp khi cuộn". Đây là chủ ý, không phải lỗi.
- Đã xem trực tiếp ảnh của S04 và S08.
- File Figma: 28/28 mở được khi tắt JavaScript, không tràn ngang; đã xem S08 desktop và S04 mobile. Không file nào chứa chấm chú thích hay script.
- **Chưa thử import thật vào Figma** (không có Figma trên máy này). Plugin khác nhau có thể dựng layer khác nhau.

## 6. Chưa kiểm tra / lưu ý

- **Chưa xem bằng mắt từng tờ.** Bìa, sơ đồ và S01–S03, S05–S07, S09–S14 mới chỉ được kiểm tra bằng bước xuất tự động (không lỗi, không bị cắt).
- **Wireframe phản ánh giao diện thật ngày 14/11/2026.** Frontend thay đổi thì sửa `SCREENS` trong file nguồn rồi chạy lại `export.mjs`.
- **Dữ liệu mẫu** (tên sinh viên, doanh nghiệp) lấy từ seed demo và là dữ liệu tổng hợp.
- **Ba lỗi nhỏ thấy trên giao diện thật (wireframe vẽ theo dạng đúng); lỗi nhãn AI lặp đã sửa trong code ngày 14/11:**
  - Nhãn khung AI bị lặp "chỉ để tham khảo".
  - Đầu trang mobile chiếm nhiều chỗ.
  - Sidebar desktop không kéo hết chiều cao khi trang dài.
