# Refactor FE: tách `web/` thành module

Nhánh: `feature/refactor-fe` (tách từ `feature/vin15-internship-assistant`)

## 1. Vấn đề trước khi refactor

Toàn bộ FE nằm trong 3 file phẳng:

| File | Số dòng | Nội dung |
|---|---|---|
| `web/index.html` | 25 | Khung trang, nạp `styles.css` và `app.js` (script thường) |
| `web/styles.css` | 85 | Toàn bộ CSS |
| `web/app.js` | 708 | Toàn bộ logic: tiện ích, API, đăng nhập, màn hình của 3 vai trò, router |

Hệ quả: dễ conflict git khi nhiều người cùng sửa, khó đọc, khó test từng phần, mọi thứ dùng chung biến toàn cục.

## 2. Cấu trúc mới

```
web/
├── index.html                  # nạp 3 file CSS + js/main.js (type="module")
├── css/
│   ├── base.css                # biến theme, reset, typography, tiện ích (.muted, .small, .pre)
│   ├── layout.css              # topbar, nav, card, lưới, responsive
│   └── components.css          # form, nút, badge, timeline, bảng, chat, toast, thông báo, login
└── js/
    ├── main.js                 # điểm vào: gắn sự kiện đăng xuất, chuông, hashchange, gọi boot()
    ├── boot.js                 # nhận token (kể cả callback SSO), tải /me + /config, vào router
    ├── router.js               # route() theo hash và vai trò
    ├── core/
    │   ├── state.js            # state dùng chung
    │   ├── config.js           # API, STATUS, SEVERITY, FIELDS, NAV
    │   ├── utils.js            # $, esc, badge, fmtDate, cite, toast, storage
    │   ├── api.js              # api(), errorText, run, openFile, streamChat (SSE)
    │   └── auth.js             # renderLogin, logout
    ├── components/
    │   ├── shell.js            # renderShell (thanh nav), refreshBell (thông báo)
    │   ├── form.js             # form đăng ký, điền tự động từ file bằng AI, showChecks
    │   ├── timeline.js         # các mốc bắt buộc, form xin gia hạn
    │   ├── outline.js          # đề cương thực tập
    │   └── decision.js         # hộp quyết định của giảng viên
    └── views/
        ├── student/            # home.js, logs.js
        ├── lecturer/           # queue.js, students.js, internship.js, flags.js
        ├── admin/              # home.js
        └── shared/             # assistant.js, policies.js (dùng chung mọi vai trò)
```

Tổng cộng: 3 file CSS và 20 file JS (gồm `main`, `boot`, `router` và các thư mục con).

## 3. Cách thực hiện

- **Giữ nguyên logic.** Code được cắt theo dòng từ `app.js` cũ bằng script; chỉ thêm `import`/`export` và comment đầu file. Không viết lại hàm nào.
- **ES modules thuần.** `index.html` dùng `<script type="module" src="js/main.js">`; không cần bundler hay build tool. Backend vẫn phục vụ `web/` bằng `StaticFiles` (`src/main.py`) như cũ.
- **Không xóa file cũ.** Bản gốc `app.js`, `styles.css` và `index.html` được chuyển vào `_legacy/web-monolith/` (thư mục gốc dự án), theo quy tắc "chuyển vào `_legacy/` thay vì xóa".
- **Tách CSS** theo vai trò: nền tảng (`base`), khung trang (`layout`), thành phần (`components`). Thứ tự nạp trong `index.html`: base → layout → components.

## 4. Kiểm tra đã làm

- Script tĩnh kiểm tra mọi `import {…}` trỏ tới file có thật và tên đó được `export`: không còn lỗi.
- Script dò identifier dùng mà chưa import: phát hiện và sửa 1 lỗi (`views/lecturer/queue.js` thiếu import `api`).

## 5. Chưa kiểm tra / lưu ý

- **Chưa chạy thử trên trình duyệt.** Máy chưa cài `sqlalchemy` nên backend không khởi động được; việc chạy server tĩnh để mở thử bị chặn. Cần chạy `uvicorn src.main:app --reload`, mở http://localhost:8000 và xem tab Console. Lỗi thường gặp nếu có: `does not provide an export`, `is not defined`.
- **Import vòng (circular).** `router.js` và các view import lẫn nhau; `core/api.js` và `core/auth.js` cũng vậy (api gọi `logout`, auth gọi `api`). Vẫn chạy được vì các import chỉ được dùng khi hàm được gọi, không phải lúc nạp module. Muốn gỡ hẳn cần thêm lớp điều hướng riêng (ví dụ `core/nav.js`), chưa làm.
- **Chưa commit.** Các thay đổi đang ở dạng chưa commit trên nhánh `feature/refactor-fe`.
- **`_legacy/web-monolith/`** có thể xóa sau khi xác nhận mọi màn hình chạy đúng.
