import { NAV } from "../core/config.js";
import { state } from "../core/state.js";
import { $, esc, fmtDate } from "../core/utils.js";
import { api } from "../core/api.js";

// Thanh điều hướng + chuông thông báo.

export function renderShell() {
  $("#topbar").hidden = false;
  const role = { student: "Sinh viên", lecturer: "Giảng viên", admin: "Quản trị viên" }[state.me.role];
  $("#who").textContent = `${state.me.full_name} · ${role}`;
  const route = location.hash.split("/").slice(0, 2).join("/") || "#/";
  $("#nav").innerHTML = NAV[state.me.role].map(([h, t]) => `<a href="${h}" class="${h === route || (h === "#/" && route === "#") ? "active" : ""}">${t}</a>`).join("");
}

export async function refreshBell() {
  try {
    const list = await api("GET", "/notifications");
    const unread = list.filter((n) => !n.read).length;
    const c = $("#bell-count");
    c.hidden = unread === 0;
    c.textContent = unread;
    $("#notif-panel").innerHTML = list.length
      ? list.map((n) => `<div class="n ${n.read ? "" : "unread"}"><a href="${esc(n.link || "#/")}">${esc(n.title)}</a>${n.body ? `<div class="muted small">${esc(n.body)}</div>` : ""}<div class="muted small">${fmtDate(n.created_at)}</div></div>`).join("")
      : `<p class="muted">Chưa có thông báo.</p>`;
  } catch (_) { /* không chặn trang */ }
}
