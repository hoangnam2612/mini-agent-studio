import { SEVERITY } from "../../core/config.js";
import { $, esc, badge, fmtDate } from "../../core/utils.js";
import { api, run } from "../../core/api.js";
import { route } from "../../router.js";

// Cảnh báo rủi ro.

export async function lecturerFlags() {
  const flags = await api("GET", "/risk-flags");
  $("#app").innerHTML = `<div class="card"><h1>Sinh viên có cảnh báo</h1><p class="small muted">Cảnh báo do tác tử giám sát sinh ra theo luật; tác tử không thay đổi trạng thái hồ sơ.</p>
    ${flags.map((f) => `<div style="border-bottom:1px solid var(--border);padding:10px 0"><div class="row spread"><div>${badge(f.severity, SEVERITY)} <a href="#/internship/${f.internship_id}">${esc(f.student.full_name)}</a> ${badge(f.status)}</div><span class="small muted">${fmtDate(f.created_at)}</span></div>
      <p>${esc(f.reason)}</p><div class="row"><input placeholder="Ghi chú (bắt buộc khi bác bỏ)" data-note="${f.id}" style="flex:1">
      ${f.status === "open" ? `<button data-flag="${f.id}" data-a="acknowledge">Ghi nhận</button>` : ""}<button class="primary" data-flag="${f.id}" data-a="resolve">Đã xử lý</button><button class="danger" data-flag="${f.id}" data-a="dismiss">Bác bỏ</button></div></div>`).join("") || `<p class="muted">Không có cảnh báo đang mở.</p>`}</div>`;
  document.querySelectorAll("[data-flag]").forEach((b) => (b.onclick = async () => {
    await run(() => api("PATCH", `/risk-flags/${b.dataset.flag}`, { action: b.dataset.a, note: $(`[data-note="${b.dataset.flag}"]`).value }), "Đã cập nhật cảnh báo");
    route();
  }));
}
