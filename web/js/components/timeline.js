import { state } from "../core/state.js";
import { $, esc, badge, fmtDate, cite } from "../core/utils.js";
import { api, run, openFile } from "../core/api.js";
import { route } from "../router.js";

// Các mốc bắt buộc + form xin gia hạn.

export function renderTimeline(i) {
  const types = state.config.evidence_types;
  $("#timeline").innerHTML = i.milestones.map((m) => {
    const canAct = state.me.role === "student" && ["pending", "overdue", "rejected"].includes(m.status) && !m.linked_to;
    const left = m.status === "accepted" ? "" : m.days_left >= 0 ? `còn ${m.days_left} ngày` : `quá ${-m.days_left} ngày`;
    return `<li class="${m.status}"><div class="row spread"><b>${esc(m.name)}</b>${badge(m.status)}</div>
      <div class="small muted">Hạn ${fmtDate(m.due_date)} ${left ? "· " + left : ""} ${m.linked_to ? "· cập nhật theo đề cương" : ""}</div>
      ${m.required_evidence.length ? `<div class="small">Minh chứng yêu cầu: ${m.required_evidence.map((t) => esc(types[t] || t)).join(", ")}</div>` : ""}
      ${m.evidence.length ? `<div class="small">Đã tải: ${m.evidence.map((e) => `<button class="link" data-file="${e.id}">${esc(e.filename)}</button>`).join(", ")}</div>` : ""}
      ${m.comment ? `<div class="small">Nhận xét GV: ${esc(m.comment)}</div>` : ""}
      ${cite(m.citation)}
      ${canAct ? `<div class="row" style="margin-top:6px">
        <select data-type="${m.id}" style="width:auto">${Object.entries(types).map(([k, v]) => `<option value="${k}" ${m.required_evidence[0] === k ? "selected" : ""}>${esc(v)}</option>`).join("")}</select>
        <input type="file" data-upload="${m.id}" accept=".pdf,.docx,.png,.jpg,.jpeg" style="width:auto">
        <button class="primary" data-submit="${m.id}">Nộp mốc</button>
        <button data-extend="${m.id}">Xin gia hạn</button></div><div data-ext-form="${m.id}"></div>` : ""}</li>`;
  }).join("");
  document.querySelectorAll("[data-file]").forEach((b) => (b.onclick = () => openFile(b.dataset.file)));
  document.querySelectorAll("[data-upload]").forEach((inp) => (inp.onchange = async () => {
    const id = inp.dataset.upload;
    const fd = new FormData(); fd.append("file", inp.files[0]); fd.append("evidence_type", $(`[data-type="${id}"]`).value);
    await run(() => api("POST", `/milestones/${id}/evidence`, fd, true), "Đã tải minh chứng"); route();
  }));
  document.querySelectorAll("[data-submit]").forEach((b) => (b.onclick = async () => {
    await run(() => api("POST", `/milestones/${b.dataset.submit}/submit`), "Đã nộp mốc"); route();
  }));
  document.querySelectorAll("[data-extend]").forEach((b) => (b.onclick = () => extensionForm(b.dataset.extend, i)));
}

export function extensionForm(milestoneId, i) {
  const m = i.milestones.find((x) => String(x.id) === String(milestoneId));
  $(`[data-ext-form="${milestoneId}"]`).innerHTML = `<div class="card" style="margin-top:8px">
    <h3>Xin gia hạn: ${esc(m.name)}</h3><p class="small muted">Hạn hiện tại ${fmtDate(m.due_date)} · mỗi lần không quá 14 ngày (QĐ-TT/2026 · Điều 10 / Khoản 2). Giảng viên phụ trách sẽ quyết định.</p>
    <div class="field"><label>Hạn mới đề xuất</label><input type="date" id="ext-date-${milestoneId}"></div>
    <div class="field"><label>Lý do</label><textarea id="ext-reason-${milestoneId}"></textarea></div>
    <div class="field"><label>Minh chứng cho lý do (tùy chọn: giấy khám bệnh, email của doanh nghiệp…)</label><input type="file" id="ext-file-${milestoneId}" accept=".pdf,.docx,.png,.jpg,.jpeg"></div>
    <button class="primary" id="ext-send-${milestoneId}">Gửi yêu cầu</button></div>`;
  $(`#ext-send-${milestoneId}`).onclick = async () => {
    const body = { requested_due_date: $(`#ext-date-${milestoneId}`).value, reason: $(`#ext-reason-${milestoneId}`).value };
    const file = $(`#ext-file-${milestoneId}`).files[0];
    if (file) {
      const fd = new FormData(); fd.append("file", file); fd.append("evidence_type", "other");
      body.evidence_id = (await run(() => api("POST", `/milestones/${milestoneId}/evidence`, fd, true))).id;
    }
    await run(() => api("POST", `/milestones/${milestoneId}/extensions`, body), "Đã gửi yêu cầu gia hạn");
    route();
  };
}
