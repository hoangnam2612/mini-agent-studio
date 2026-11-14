import { SEVERITY } from "../../core/config.js";
import { state } from "../../core/state.js";
import { $, esc, badge, fmtDate } from "../../core/utils.js";
import { api, run } from "../../core/api.js";
import { route } from "../../router.js";
import { renderForm } from "../../components/form.js";
import { renderTimeline } from "../../components/timeline.js";
import { renderOutline } from "../../components/outline.js";

// Trang chủ sinh viên: hồ sơ, mốc, đề cương, gia hạn.

export async function studentHome() {
  const list = await api("GET", "/internships");
  if (!list.length) {
    $("#app").innerHTML = `<div class="card"><h1>Hồ sơ thực tập</h1><p>Bạn chưa có hồ sơ trong đợt <b>${esc(state.config.cohort.name)}</b>.</p>
      <p class="muted small">Khung thời gian: ${fmtDate(state.config.cohort.start_window)} – ${fmtDate(state.config.cohort.end_window)} · tối thiểu ${state.config.cohort.min_weeks} tuần</p>
      <button class="primary" id="create">Tạo hồ sơ đăng ký</button></div>`;
    $("#create").onclick = async () => { await run(() => api("POST", "/internships", {}), "Đã tạo hồ sơ nháp"); route(); };
    return;
  }
  const i = await api("GET", `/internships/${list[0].id}`);
  const [flags, extensions] = await Promise.all([api("GET", "/risk-flags"), api("GET", `/internships/${i.id}/extensions`)]);
  const editable = ["draft", "revision_requested"].includes(i.status);
  $("#app").innerHTML = `
    <div class="card"><div class="row spread"><h1>Hồ sơ thực tập ${badge(i.status)}</h1><span class="muted small">GV phụ trách: ${esc(i.lecturer?.full_name || "chưa phân công")}</span></div>
      ${i.decision_reason ? `<p class="${i.status === "revision_requested" ? "errors" : "muted"}">Nhận xét của GV: ${esc(i.decision_reason)}</p>` : ""}
      ${flags.length ? `<div>${flags.map((f) => `<p>${badge(f.severity, SEVERITY)} ${esc(f.reason)}</p>`).join("")}</div>` : ""}
    </div>
    <div class="card" id="form-card"></div>
    ${i.milestones.length ? `<div class="card"><h2>Các mốc bắt buộc</h2><ul class="timeline" id="timeline"></ul></div>` : ""}
    ${["approved", "in_progress", "completed"].includes(i.status) ? `<div class="card" id="outline-card"></div>` : ""}
    ${extensions.length ? `<div class="card"><h2>Yêu cầu gia hạn</h2>${extensions.map(extRow).join("")}</div>` : ""}`;
  renderForm(i, editable);
  if (i.milestones.length) renderTimeline(i);
  if ($("#outline-card")) renderOutline(i);
  document.querySelectorAll("[data-cancel-ext]").forEach((b) => (b.onclick = async () => {
    await run(() => api("POST", `/extensions/${b.dataset.cancelExt}/cancel`), "Đã hủy yêu cầu"); route();
  }));
}

export function extRow(e) {
  return `<div class="row spread" style="border-bottom:1px solid var(--border);padding:8px 0">
    <div><b>${esc(e.milestone.name)}</b> ${badge(e.status)}<div class="small muted">${fmtDate(e.previous_due_date)} → ${fmtDate(e.requested_due_date)} · ${esc(e.reason)}</div>
    ${e.decision_reason ? `<div class="small">GV: ${esc(e.decision_reason)}</div>` : ""}</div>
    ${e.status === "open" && state.me.role === "student" ? `<button class="danger" data-cancel-ext="${e.id}">Hủy</button>` : ""}</div>`;
}
