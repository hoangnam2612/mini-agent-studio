import { state } from "../../core/state.js";
import { $, esc, badge, fmtDate } from "../../core/utils.js";
import { api, run, openFile } from "../../core/api.js";
import { route } from "../../router.js";

// Chi tiết một hồ sơ thực tập (GV / QTV).

export async function lecturerInternship(id) {
  const canReview = state.me.role === "lecturer"; // QTV chỉ xem, không duyệt (HITL thuộc GV phụ trách)
  const [i, logs, audit] = await Promise.all([api("GET", `/internships/${id}`), api("GET", `/internships/${id}/logs`), api("GET", `/internships/${id}/audit`)]);
  $("#app").innerHTML = `<div class="card"><div class="row spread"><h1>${esc(i.student.full_name)} ${badge(i.status)}</h1><a href="#/students">← Danh sách</a></div>
      <p class="muted">${esc(i.company_name)} · ${esc(i.position)} · ${fmtDate(i.start_date)} – ${fmtDate(i.end_date)}</p></div>
    ${i.milestones.length ? `<div class="card"><h2>Mốc</h2><ul class="timeline">${i.milestones.map((m) => `<li class="${m.status}"><div class="row spread"><b>${esc(m.name)}</b>${badge(m.status)}</div>
      <div class="small muted">Hạn ${fmtDate(m.due_date)}</div>
      ${m.evidence.length ? `<div class="small">Minh chứng: ${m.evidence.map((e) => `<button class="link" data-file="${e.id}">${esc(e.filename)}</button>`).join(", ")}</div>` : ""}
      ${canReview && m.status === "submitted" && !m.linked_to ? `<div class="row" style="margin-top:6px"><input placeholder="Nhận xét (bắt buộc khi trả lại)" data-mcomment="${m.id}" style="flex:1"><button class="primary" data-mreview="${m.id}" data-d="accepted">Chấp nhận</button><button class="danger" data-mreview="${m.id}" data-d="rejected">Trả lại</button></div>` : ""}</li>`).join("")}</ul></div>` : ""}
    ${i.outline ? `<div class="card"><h2>Đề cương ${badge(i.outline.status)}</h2><p class="pre">${esc(i.outline.content)}</p>${i.outline.reason ? `<p class="small">Nhận xét: ${esc(i.outline.reason)}</p>` : ""}</div>` : ""}
    <div class="card"><h2>Nhật ký (${logs.reduce((s, l) => s + l.hours, 0)} giờ)</h2><div class="table-wrap"><table><tr><th>Tuần</th><th>Nội dung</th><th>Giờ</th><th>Trạng thái</th></tr>
      ${logs.map((l) => `<tr><td>${l.week_no}</td><td class="pre">${esc(l.content)}${l.difficulties ? `<div class="small muted">Khó khăn: ${esc(l.difficulties)}</div>` : ""}
        ${canReview && l.review_status === "pending" ? `<div class="row" style="margin-top:6px"><input placeholder="Nhận xét" data-lcomment="${l.id}" style="flex:1"><button data-lreview="${l.id}" data-d="accepted">Chấp nhận</button><button class="danger" data-lreview="${l.id}" data-d="returned">Trả lại</button></div>` : l.comment ? `<div class="small">GV: ${esc(l.comment)}</div>` : ""}</td>
        <td>${l.hours}</td><td>${badge(l.review_status)}</td></tr>`).join("") || `<tr><td colspan="4" class="muted">Chưa có nhật ký.</td></tr>`}</table></div></div>
    <div class="card"><h2>Lịch sử thao tác (audit)</h2><div class="table-wrap"><table><tr><th>Thời điểm</th><th>Người</th><th>Đối tượng</th><th>Hành động</th><th>Lý do</th></tr>
      ${audit.map((a) => `<tr class="small"><td>${new Date(a.at + "Z").toLocaleString("vi-VN")}</td><td>${esc(a.actor)}</td><td>${esc(a.entity)} #${a.entity_id ?? ""}</td><td>${esc(a.action)}</td><td>${esc(a.reason)}</td></tr>`).join("")}</table></div></div>`;
  document.querySelectorAll("[data-file]").forEach((b) => (b.onclick = () => openFile(b.dataset.file)));
  document.querySelectorAll("[data-mreview]").forEach((b) => (b.onclick = async () => {
    await run(() => api("POST", `/milestones/${b.dataset.mreview}/review`, { decision: b.dataset.d, comment: $(`[data-mcomment="${b.dataset.mreview}"]`).value }), "Đã cập nhật mốc");
    route();
  }));
  document.querySelectorAll("[data-lreview]").forEach((b) => (b.onclick = async () => {
    await run(() => api("POST", `/logs/${b.dataset.lreview}/review`, { decision: b.dataset.d, comment: $(`[data-lcomment="${b.dataset.lreview}"]`).value }), "Đã cập nhật nhật ký");
    route();
  }));
}
