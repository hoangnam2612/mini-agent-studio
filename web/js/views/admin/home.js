import { $, esc, toast } from "../../core/utils.js";
import { api, run } from "../../core/api.js";
import { route } from "../../router.js";

// Trang quản trị: mẫu mốc, phân công GV, tạo tài khoản.

export async function adminHome() {
  const [users, cohort] = await Promise.all([api("GET", "/admin/users"), api("GET", "/admin/cohort")]);
  const lecturers = users.filter((u) => u.role === "lecturer");
  $("#app").innerHTML = `<div class="card"><div class="row spread"><h1>Quản trị</h1><button id="run-monitor">Chạy giám sát ngay</button></div>
      <p class="muted">Đợt: ${esc(cohort.name)} (${esc(cohort.code)})</p></div>
    <div class="card"><h2>Mẫu mốc của đợt</h2><p class="small muted">Thay đổi chỉ áp dụng cho hồ sơ được duyệt sau thời điểm lưu; mốc đã sinh giữ nguyên.</p>
      <div class="table-wrap"><table id="tpl-table"><tr><th>Mã</th><th>Tên mốc</th><th>Mốc tính hạn</th><th>Lệch (ngày)</th><th>Minh chứng yêu cầu</th><th>Căn cứ</th><th></th></tr>
      ${cohort.templates.map(templateRow).join("")}</table></div>
      <div class="row" style="margin-top:8px"><button id="tpl-add">Thêm mốc</button><button class="primary" id="tpl-save">Lưu mẫu mốc</button></div></div>
    <div class="card"><h2>Phân công giảng viên</h2><div class="table-wrap"><table><tr><th>Sinh viên</th><th>Mã SV</th><th>GV phụ trách</th></tr>
      ${users.filter((u) => u.role === "student").map((s) => `<tr><td>${esc(s.full_name)}</td><td>${esc(s.student_code)}</td><td><select data-assign="${s.id}">${lecturers.map((l) => `<option value="${l.id}" ${l.id === s.lecturer_id ? "selected" : ""}>${esc(l.full_name)}</option>`).join("")}</select></td></tr>`).join("")}</table></div></div>
    <div class="card"><h2>Thêm tài khoản</h2><form id="user-form"><div class="grid2">
      <div class="field"><label>Tên đăng nhập</label><input name="username" required pattern="[a-z0-9_.]+"></div><div class="field"><label>Mật khẩu</label><input name="password" type="password" minlength="6" required></div>
      <div class="field"><label>Họ tên</label><input name="full_name" required></div><div class="field"><label>Vai trò</label><select name="role"><option value="student">Sinh viên</option><option value="lecturer">Giảng viên</option></select></div>
      <div class="field"><label>Email</label><input name="email"></div><div class="field"><label>Mã SV</label><input name="student_code"></div></div>
      <button class="primary">Tạo tài khoản</button></form></div>`;
  const bindRemove = () => document.querySelectorAll("[data-tpl-del]").forEach((b) => (b.onclick = () => b.closest("tr").remove()));
  bindRemove();
  $("#tpl-add").onclick = () => {
    $("#tpl-table").insertAdjacentHTML("beforeend", templateRow({ code: "", name: "", anchor: "start", offset_days: 7, required_evidence: [], linked_to: null, citation: {} }));
    bindRemove();
  };
  $("#tpl-save").onclick = async () => {
    const rows = [...document.querySelectorAll("#tpl-table tr[data-tpl]")].map((tr) => {
      const v = (k) => tr.querySelector(`[data-k="${k}"]`).value.trim();
      const [doc, ...path] = v("citation").split("·").map((s) => s.trim());
      return {
        code: v("code"), name: v("name"), anchor: v("anchor"), offset_days: Number(v("offset_days")),
        required_evidence: v("required_evidence") ? v("required_evidence").split(",").map((s) => s.trim()).filter(Boolean) : [],
        linked_to: tr.dataset.linked || null, citation: doc ? { doc, path: path.join(" · ") } : {},
      };
    });
    await run(() => api("PUT", "/admin/cohort/templates", rows), "Đã lưu mẫu mốc");
    route();
  };
  $("#run-monitor").onclick = async () => { const r = await run(() => api("POST", "/monitor/run")); toast(`Giám sát xong: ${r.flags_created} cảnh báo mới, ${r.overdue} mốc quá hạn`); };
  document.querySelectorAll("[data-assign]").forEach((s) => (s.onchange = () => run(() => api("POST", "/admin/assign", { student_id: Number(s.dataset.assign), lecturer_id: Number(s.value) }), "Đã phân công")));
  $("#user-form").onsubmit = async (ev) => {
    ev.preventDefault();
    const body = Object.fromEntries(new FormData(ev.target));
    if (!body.student_code) delete body.student_code;
    await run(() => api("POST", "/admin/users", body), "Đã tạo tài khoản");
    route();
  };
}

export function templateRow(t) {
  const anchors = { start: "Ngày bắt đầu", mid: "Giữa kỳ", end: "Ngày kết thúc" };
  const citation = t.citation?.doc ? `${t.citation.doc} · ${t.citation.path}` : "";
  return `<tr data-tpl="1" data-linked="${esc(t.linked_to || "")}">
    <td><input data-k="code" value="${esc(t.code)}" style="min-width:90px"></td>
    <td><input data-k="name" value="${esc(t.name)}" style="min-width:200px"></td>
    <td><select data-k="anchor">${Object.entries(anchors).map(([k, l]) => `<option value="${k}" ${t.anchor === k ? "selected" : ""}>${l}</option>`).join("")}</select></td>
    <td><input data-k="offset_days" type="number" value="${t.offset_days}" style="width:80px"></td>
    <td><input data-k="required_evidence" value="${esc(t.required_evidence.join(", "))}" placeholder="${t.linked_to ? "theo đề cương" : "vd final_report"}" ${t.linked_to ? "disabled" : ""}></td>
    <td><input data-k="citation" value="${esc(citation)}" placeholder="QĐ-TT/2026 · Điều 7 / Khoản 1"></td>
    <td><button class="danger" data-tpl-del="1" title="Xóa mốc">✕</button></td></tr>`;
}
