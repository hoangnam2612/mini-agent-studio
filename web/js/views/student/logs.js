import { $, esc, badge } from "../../core/utils.js";
import { api, run, openFile } from "../../core/api.js";
import { route } from "../../router.js";

// Nhật ký tuần của sinh viên.

export async function studentLogs() {
  const list = await api("GET", "/internships");
  const i = list[0];
  if (!i || !["approved", "in_progress", "completed"].includes(i.status)) {
    $("#app").innerHTML = `<div class="card"><h1>Nhật ký tuần</h1><p class="muted">Nhật ký mở sau khi hồ sơ đăng ký được duyệt.</p></div>`;
    return;
  }
  const logs = await api("GET", `/internships/${i.id}/logs`);
  const total = logs.reduce((s, l) => s + l.hours, 0);
  const next = logs.length ? Math.max(...logs.map((l) => l.week_no)) + 1 : 1;
  $("#app").innerHTML = `<div class="card"><h1>Nhật ký tuần</h1><p class="muted">Tổng ${total} giờ · quy chế: trung bình ${i.mode === "part_time" ? 16 : 32} giờ/tuần (QĐ-TT/2026 · Điều 8 / Khoản 2)</p>
    ${i.status !== "completed" ? `<div class="grid2"><div class="field"><label>Tuần</label><input type="number" id="l-week" min="1" value="${next}"></div><div class="field"><label>Số giờ</label><input type="number" id="l-hours" min="0" max="80" step="0.5"></div></div>
    <div class="field"><label>Công việc đã làm</label><textarea id="l-content"></textarea></div>
    <div class="field"><label>Khó khăn</label><textarea id="l-diff" style="min-height:60px"></textarea></div>
    <button class="primary" id="l-save">Ghi nhật ký</button>` : ""}</div>
    <div class="card"><div class="table-wrap"><table><tr><th>Tuần</th><th>Nội dung</th><th>Giờ</th><th>Trạng thái</th></tr>
    ${logs.map((l) => `<tr><td>${l.week_no}</td><td class="pre">${esc(l.content)}${l.comment ? `<div class="small muted">GV: ${esc(l.comment)}</div>` : ""}
      ${l.attachments.length ? `<div class="small">Đính kèm: ${l.attachments.map((e) => `<button class="link" data-file="${e.id}">${esc(e.filename)}</button>`).join(", ")}</div>` : ""}
      ${l.review_status !== "accepted" ? `<div class="row small"><label class="row" style="margin:0">Đính kèm file <input type="file" data-log-file="${l.id}" accept=".pdf,.docx,.png,.jpg,.jpeg" style="width:auto"></label></div>` : ""}
      ${l.review_status === "returned" ? `<div><button class="link" data-edit-log="${l.id}">Sửa & gửi lại</button></div>` : ""}</td><td>${l.hours}</td><td>${badge(l.review_status)}</td></tr>`).join("") || `<tr><td colspan="4" class="muted">Chưa có nhật ký.</td></tr>`}
    </table></div></div>`;
  if ($("#l-save")) $("#l-save").onclick = async () => {
    await run(() => api("POST", `/internships/${i.id}/logs`, {
      week_no: Number($("#l-week").value), hours: Number($("#l-hours").value), content: $("#l-content").value, difficulties: $("#l-diff").value,
    }), "Đã ghi nhật ký");
    route();
  };
  document.querySelectorAll("[data-file]").forEach((b) => (b.onclick = () => openFile(b.dataset.file)));
  document.querySelectorAll("[data-log-file]").forEach((inp) => (inp.onchange = async () => {
    const fd = new FormData(); fd.append("file", inp.files[0]);
    await run(() => api("POST", `/logs/${inp.dataset.logFile}/attachments`, fd, true), "Đã đính kèm file");
    route();
  }));
  document.querySelectorAll("[data-edit-log]").forEach((b) => (b.onclick = async () => {
    const l = logs.find((x) => String(x.id) === b.dataset.editLog);
    const content = prompt("Nội dung nhật ký đã bổ sung:", l.content);
    if (!content) return;
    await run(() => api("PATCH", `/logs/${l.id}`, { week_no: l.week_no, content, difficulties: l.difficulties, hours: l.hours }), "Đã gửi lại");
    route();
  }));
}
