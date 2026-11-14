import { STATUS } from "./config.js";

// Tiện ích DOM / định dạng / toast / localStorage.

export const $ = (sel, root = document) => root.querySelector(sel);
export const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
export const badge = (status, map = STATUS) => { const [t, cls] = map[status] || [status, ""]; return `<span class="badge ${cls}">${esc(t)}</span>`; };
export const fmtDate = (iso) => (iso ? new Date(iso.length === 10 ? iso + "T00:00:00" : iso).toLocaleDateString("vi-VN") : "—");
export const cite = (c) => (c && c.doc ? `<span class="small muted">Căn cứ: ${esc(c.doc)} · ${esc(c.path)}</span>` : "");

export function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toast.t);
  toast.t = setTimeout(() => (el.hidden = true), 4000);
}

export function storage(op, key, value) {
  try {
    if (op === "get") return localStorage.getItem(key);
    if (op === "set") localStorage.setItem(key, value);
    if (op === "del") localStorage.removeItem(key);
  } catch (_) { /* chế độ riêng tư: bỏ qua */ }
  return null;
}
