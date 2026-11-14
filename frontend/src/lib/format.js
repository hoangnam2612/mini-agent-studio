// Định dạng ngày, lưu trữ cục bộ.

export const fmtDate = (iso) =>
  iso ? new Date(iso.length === 10 ? iso + "T00:00:00" : iso).toLocaleDateString("vi-VN") : "—";

export const fmtDateTime = (iso) => new Date(iso + "Z").toLocaleString("vi-VN");

export const initials = (name = "") =>
  name.trim().split(/\s+/).slice(-2).map((w) => w[0]).join("").toUpperCase() || "?";

export function storage(op, key, value) {
  try {
    if (op === "get") return localStorage.getItem(key);
    if (op === "set") localStorage.setItem(key, value);
    if (op === "del") localStorage.removeItem(key);
  } catch (_) { /* chế độ riêng tư: bỏ qua */ }
  return null;
}
