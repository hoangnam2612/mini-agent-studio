// Áp theme đã lưu trước khi vẽ trang (tránh nháy sáng→tối).
// File riêng thay vì <script> inline: CSP của Caddy (script-src 'self') chặn script inline.
try {
  var t = localStorage.getItem("vin15_theme");
  if (t === "light" || t === "dark") document.documentElement.dataset.theme = t;
} catch (e) {}
