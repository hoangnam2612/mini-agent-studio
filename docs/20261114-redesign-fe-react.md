# Thiết kế lại giao diện và chuyển FE sang React

Nhánh: `feature/refactor-fe`

## 1. Mục tiêu

- Giao diện cũ trông "máy móc": nền xám, nút mặc định, thanh nav trên cùng, emoji làm icon. Cần giao diện thân thiện với sinh viên và giảng viên.
- Giữ nguyên chức năng và luồng màn hình; chỉ đổi diện mạo.
- Viết lại FE bằng React để dễ bảo trì (component hoá, không còn nối chuỗi HTML).

## 2. Thiết kế (canvas)

Bản thiết kế 4 màn (Đăng nhập, Sinh viên, Giảng viên, Trợ lý AI): https://claude.ai/artifact/7gtcgrgu2XZPMbgLEXxwoR (riêng tư, chỉ chủ tài khoản mở được cho đến khi chia sẻ).

Màu giữ đúng như canvas (nền kem `#F6F4EE`, xanh `#1F4B99`, AI màu xanh ngọc `#0B5F58`). Phần chữ và khung được tinh chỉnh thêm trong code:
- Chữ: Lexend (một họ duy nhất, có tiếng Việt), tương phản bằng độ đậm và cỡ chữ.
- Sidebar trắng, mục đang chọn nền xanh nhạt có vạch xanh bên trái; khung nội dung viền rõ, bo góc nhỏ, không đổ bóng.
- Điểm nhấn: lộ trình mốc — các chặng đánh số nối bằng đường dày, chặng đã xong tô xanh, chặng hiện tại to hơn, tô xanh đậm có viền sáng; đầu trang sinh viên có dòng "Việc tiếp theo" (tên mốc, hạn, số ngày còn lại).
- Nút tối thiểu 46px, focus hiện rõ, tôn trọng `prefers-reduced-motion`.
- Sáng/tối: nút chọn Tự động / Sáng / Tối (`components/ui/ThemeToggle.jsx`, `hooks/useTheme.js`) ở sidebar và trang đăng nhập; lưu ở localStorage (`vin15_theme`), script nhỏ trong `index.html` áp theme trước khi vẽ trang. Màu tối nằm trong `styles/base.css`.
- Chi tiết nhỏ (font, khung) có khác canvas một chút; canvas chưa cập nhật theo.

## 3. Cấu trúc code (`frontend/`)

```
frontend/
├── index.html, vite.config.js, package.json
└── src/
    ├── main.jsx, App.jsx            # điểm vào + bảng route theo vai trò (HashRouter)
    ├── styles/                      # base.css (design tokens), layout.css, components.css
    ├── lib/                         # api.js (REST + SSE), config.js (STATUS, FIELDS, NAV), format.js
    ├── context/                     # AuthContext, ToastContext (run), ChatContext
    ├── hooks/useAsync.js            # tải dữ liệu + reload()
    ├── components/ui/               # Badge, Button, Card, Field, Alert, AiBox, Icon…
    ├── components/layout/           # AppShell (sidebar), Notifications
    └── features/
        ├── auth/Login.jsx
        ├── student/                 # StudentHome, RegistrationForm, Timeline, Outline, ExtensionList, StudentLogs
        ├── lecturer/                # LecturerQueue, DecisionBox, StudentList, InternshipDetail, Flags
        ├── admin/AdminHome.jsx
        └── shared/                  # Assistant, Policies, EvidenceLink
```

Muốn đổi màu/cỡ chữ: sửa `styles/base.css`. Thêm trang: thêm `<Route>` trong `App.jsx` và 1 dòng NAV trong `lib/config.js`.

## 4. Chạy

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173, proxy /api → http://localhost:8000
npm run build    # ra frontend/dist
```

Backend (`src/main.py`) tự phục vụ `frontend/dist` nếu đã build, nếu chưa thì dùng `web/` cũ. `Dockerfile` có thêm stage Node để build FE khi tạo image.

URL vẫn dạng `#/...` (HashRouter) nên callback SSO `#/sso/<token>` và `#/sso-error/<lý do>` giữ nguyên.

## 5. Đã kiểm tra

- `npm run build` thành công (63 module).
- Mở trang đăng nhập bằng Vite dev server: render đúng, không lỗi console.

## 6. Chưa kiểm tra / lưu ý

- **Chưa chạy cùng backend**: máy chưa cài dependency Python (`sqlalchemy`…) nên chưa thử đăng nhập và các màn sau đăng nhập. Cần `uvicorn src.main:app --reload` rồi thử 3 vai trò (`sv03`, `gv01`, `admin`, mật khẩu `demo123`).
- Các màn sau đăng nhập mới chỉ được kiểm tra bằng build, chưa nhìn bằng mắt.
- `Dockerfile` cần `frontend/package-lock.json` (đã có sau `npm install`); chưa build thử image.
- `web/` cũ và `_legacy/` vẫn giữ làm phương án dự phòng; xoá sau khi xác nhận bản React chạy đúng.
- Màn Trợ lý/Sinh viên/Giảng viên trong bản thiết kế là bản tĩnh với dữ liệu mẫu; màn Admin, Quy định, Danh sách SV, Chi tiết hồ sơ, Cảnh báo, Nhật ký dùng cùng bộ thành phần nhưng chưa có artboard riêng.

## 7. Sửa sau khi merge (2026-11-14, chưa commit)

- **CSP chặn font và script theme khi chạy qua HTTPS (Caddy).** CSP của `deploy/Caddyfile` chỉ cho style/script từ chính trang, nên stylesheet Lexend từ Google Fonts và đoạn `<script>` inline áp theme trong `index.html` đều bị chặn → giao diện dùng font dự phòng, người chọn theme tối thấy trang nháy sáng.
  - CSP thêm `https://fonts.googleapis.com` (style) và `font-src https://fonts.gstatic.com`; vẫn không cho script inline.
  - Script theme chuyển sang `frontend/public/theme-init.js`, nạp bằng `<script src>` trong `<head>`.
  - Kiểm tra: `tests/ui/mobile-check.mjs` qua `https://localhost` — 11/11 màn không tràn ngang, không lỗi console (trước khi sửa: lỗi CSP trên mọi màn).
- **Nhãn khung AI bị lặp** "chỉ để tham khảo" ở hàng chờ duyệt: backend đã trả nhãn đầy đủ, `LecturerQueue.jsx` không nối thêm hậu tố nữa.
- **Chưa có kiểm thử chức năng tự động cho bản React.** `tests/ui/ui-smoke.mjs` (jsdom) chỉ chạy với bản JS cũ trong `web/` (cần `/app.js`).
