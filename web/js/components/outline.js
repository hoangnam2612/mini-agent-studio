import { state } from "../core/state.js";
import { $, esc, badge } from "../core/utils.js";
import { api, run } from "../core/api.js";
import { route } from "../router.js";

// Đề cương thực tập (sinh viên).

export function renderOutline(i) {
  const o = i.outline;
  const canSubmit = state.me.role === "student" && (!o || ["revision_requested", "rejected"].includes(o.status));
  $("#outline-card").innerHTML = `<h2>Đề cương thực tập ${o ? badge(o.status) : ""}</h2>
    ${o?.reason ? `<p class="${o.status === "approved" ? "muted" : "errors"}">Nhận xét GV: ${esc(o.reason)}</p>` : ""}
    ${canSubmit ? `<div class="field"><label>Mục tiêu, nhiệm vụ, kế hoạch theo tuần, kết quả dự kiến (tối thiểu 50 ký tự)</label><textarea id="outline-text" style="min-height:160px">${esc(o?.content || "")}</textarea></div>
      <button class="primary" id="outline-send">Nộp đề cương</button>` : `<p class="pre">${esc(o?.content || "")}</p>`}`;
  if (canSubmit) $("#outline-send").onclick = async () => {
    await run(() => api("POST", `/internships/${i.id}/outline`, { content: $("#outline-text").value }), "Đã nộp đề cương"); route();
  };
}
