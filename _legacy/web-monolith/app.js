/* Cổng thực tập VIN-15 — SPA thuần JS, gọi REST /api/v1. Router theo hash. */
"use strict";

const API = "/api/v1";
const state = { token: null, me: null, config: null, conversationId: null, chat: [] };

const STATUS = {
  draft: ["Nháp", ""], submitted: ["Chờ duyệt", "info"], revision_requested: ["Cần chỉnh sửa", "warn"],
  approved: ["Đã duyệt", "ok"], rejected: ["Từ chối", "bad"], in_progress: ["Đang thực tập", "info"],
  completed: ["Hoàn thành", "ok"], pending: ["Chưa nộp", ""], overdue: ["Quá hạn", "bad"],
  accepted: ["Đã chấp nhận", "ok"], returned: ["Trả lại", "warn"], open: ["Chờ duyệt", "info"],
  cancelled: ["Đã hủy", ""], acknowledged: ["Đã ghi nhận", "info"], resolved: ["Đã xử lý", "ok"],
  dismissed: ["Bác bỏ", ""], active: ["Đang hiệu lực", "ok"], superseded: ["Đã bị thay thế", "warn"],
};
const SEVERITY = { info: ["Thông tin", "info"], warning: ["Cảnh báo", "warn"], critical: ["Nghiêm trọng", "bad"] };
const FIELDS = [
  ["company_name", "Tên doanh nghiệp"], ["company_tax_code", "Mã số thuế"], ["company_address", "Địa chỉ doanh nghiệp"],
  ["position", "Vị trí thực tập"], ["mentor_name", "Người hướng dẫn tại DN"], ["mentor_email", "Email người hướng dẫn"],
  ["mentor_phone", "SĐT người hướng dẫn"], ["start_date", "Ngày bắt đầu", "date"], ["end_date", "Ngày kết thúc", "date"],
  ["mode", "Hình thức", "mode"], ["job_description", "Mô tả công việc", "textarea"],
];

// ------------------------------------------------------------------ tiện ích
const $ = (sel, root = document) => root.querySelector(sel);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const badge = (status, map = STATUS) => { const [t, cls] = map[status] || [status, ""]; return `<span class="badge ${cls}">${esc(t)}</span>`; };
const fmtDate = (iso) => (iso ? new Date(iso.length === 10 ? iso + "T00:00:00" : iso).toLocaleDateString("vi-VN") : "—");
const cite = (c) => (c && c.doc ? `<span class="small muted">Căn cứ: ${esc(c.doc)} · ${esc(c.path)}</span>` : "");

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toast.t);
  toast.t = setTimeout(() => (el.hidden = true), 4000);
}

function storage(op, key, value) {
  try {
    if (op === "get") return localStorage.getItem(key);
    if (op === "set") localStorage.setItem(key, value);
    if (op === "del") localStorage.removeItem(key);
  } catch (_) { /* chế độ riêng tư: bỏ qua */ }
  return null;
}

async function api(method, path, body, isForm = false) {
  const headers = {};
  if (state.token) headers.Authorization = "Bearer " + state.token;
  if (body && !isForm) headers["Content-Type"] = "application/json";
  const res = await fetch(API + path, { method, headers, body: body ? (isForm ? body : JSON.stringify(body)) : undefined });
  if (res.status === 401 && state.token) { logout(); throw new Error("Phiên đăng nhập hết hạn"); }
  const data = res.headers.get("content-type")?.includes("json") ? await res.json() : null;
  if (!res.ok) {
    const err = new Error(errorText(data?.detail) || `Lỗi ${res.status}`);
    err.detail = data?.detail;
    err.status = res.status;
    throw err;
  }
  return data;
}

function errorText(detail) {
  if (!detail) return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => `${(d.loc || []).slice(-1)[0]}: ${d.msg}`).join("; ");
  if (detail.message) return detail.message + (detail.citation ? ` (${detail.citation.doc} · ${detail.citation.path})` : "");
  return JSON.stringify(detail);
}

async function run(fn, okMsg) {
  try { const r = await fn(); if (okMsg) toast(okMsg); return r; }
  catch (e) { toast(e.message); throw e; }
}

async function openFile(evidenceId) {
  const { url } = await run(() => api("GET", `/evidence/${evidenceId}/url`));
  window.open(url, "_blank", "noopener");
}

// ------------------------------------------------------------------ đăng nhập & khung
function renderLogin() {
  $("#topbar").hidden = true;
  $("#app").innerHTML = `
    <div class="card login">
      <h1>Cổng thực tập</h1>
      <p class="muted">Hệ thống hỗ trợ thực tập bằng AI (VIN-15)</p>
      <form id="login-form">
        <div class="field"><label for="u">Tên đăng nhập</label><input id="u" autocomplete="username" required></div>
        <div class="field"><label for="p">Mật khẩu</label><input id="p" type="password" autocomplete="current-password" required></div>
        <button class="primary" type="submit">Đăng nhập</button>
      </form>
      <div id="sso"></div>
      <div class="demo-accounts muted"><p>Tài khoản demo (mật khẩu <code>demo123</code>):</p>
        <p>Sinh viên: <code>sv01</code> (chưa có hồ sơ), <code>sv03</code>, <code>sv04</code>, <code>sv05</code>, <code>sv06</code><br>
        Giảng viên: <code>gv01</code> (điều phối), <code>gv02</code>, <code>gv03</code><br>Quản trị viên (tùy chọn): <code>admin</code></p></div>
    </div>`;
  api("GET", "/auth/oidc/config").then((c) => {
    if (c.enabled) $("#sso").innerHTML = `<p style="margin-top:12px"><a class="badge info" href="${API}/auth/oidc/login">Đăng nhập bằng tài khoản trường (SSO)</a></p>`;
  }).catch(() => {});
  $("#login-form").onsubmit = async (ev) => {
    ev.preventDefault();
    const r = await run(() => api("POST", "/auth/login", { username: $("#u").value.trim().toLowerCase(), password: $("#p").value }));
    state.token = r.token;
    storage("set", "vin15_token", r.token);
    await boot();
  };
}

function logout() {
  state.token = null; state.me = null; state.conversationId = null; state.chat = [];
  storage("del", "vin15_token");
  location.hash = "#/";
  renderLogin();
}

const NAV = {
  student: [["#/", "Hồ sơ của tôi"], ["#/logs", "Nhật ký"], ["#/assistant", "Trợ lý AI"], ["#/policies", "Quy định"]],
  lecturer: [["#/", "Hàng chờ duyệt"], ["#/students", "Sinh viên"], ["#/flags", "Cảnh báo"], ["#/assistant", "Trợ lý AI"], ["#/policies", "Quy định"]],
  admin: [["#/", "Quản trị"], ["#/students", "Danh sách"], ["#/policies", "Quy định"], ["#/assistant", "Trợ lý AI"]],
};

function renderShell() {
  $("#topbar").hidden = false;
  const role = { student: "Sinh viên", lecturer: "Giảng viên", admin: "Quản trị viên" }[state.me.role];
  $("#who").textContent = `${state.me.full_name} · ${role}`;
  const route = location.hash.split("/").slice(0, 2).join("/") || "#/";
  $("#nav").innerHTML = NAV[state.me.role].map(([h, t]) => `<a href="${h}" class="${h === route || (h === "#/" && route === "#") ? "active" : ""}">${t}</a>`).join("");
}

async function refreshBell() {
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

// ------------------------------------------------------------------ SINH VIÊN
async function studentHome() {
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

function extRow(e) {
  return `<div class="row spread" style="border-bottom:1px solid var(--border);padding:8px 0">
    <div><b>${esc(e.milestone.name)}</b> ${badge(e.status)}<div class="small muted">${fmtDate(e.previous_due_date)} → ${fmtDate(e.requested_due_date)} · ${esc(e.reason)}</div>
    ${e.decision_reason ? `<div class="small">GV: ${esc(e.decision_reason)}</div>` : ""}</div>
    ${e.status === "open" && state.me.role === "student" ? `<button class="danger" data-cancel-ext="${e.id}">Hủy</button>` : ""}</div>`;
}

function fieldInput(name, label, type, value, disabled, ai) {
  const dis = disabled ? "disabled" : "";
  let input;
  if (type === "textarea") input = `<textarea id="f-${name}" ${dis}>${esc(value)}</textarea>`;
  else if (type === "mode") input = `<select id="f-${name}" ${dis}><option value="full_time" ${value === "full_time" ? "selected" : ""}>Toàn thời gian</option><option value="part_time" ${value === "part_time" ? "selected" : ""}>Bán thời gian</option></select>`;
  else input = `<input id="f-${name}" type="${type === "date" ? "date" : "text"}" value="${esc(value)}" ${dis}>`;
  return `<div class="field ${ai ? "ai" : ""}" data-field="${name}"><label for="f-${name}">${label}${ai ? '<span class="ai-tag">✦ AI điền — hãy kiểm tra</span>' : ""}</label>${input}</div>`;
}

function renderForm(i, editable) {
  const ai = new Set(i.ai_fields || []);
  $("#form-card").innerHTML = `
    <div class="row spread"><h2>Thông tin đăng ký</h2>${editable ? `<label class="row" style="margin:0"><span class="badge info">✦ Điền từ file giấy tiếp nhận</span><input type="file" id="intake" accept=".pdf,.docx,.txt" style="width:auto"></label>` : ""}</div>
    <div id="intake-result"></div>
    <div class="grid2">${FIELDS.filter((f) => f[0] !== "job_description").map(([n, l, t]) => fieldInput(n, l, t, i[n] || (n === "mode" ? "full_time" : ""), !editable, ai.has(n))).join("")}</div>
    ${fieldInput("job_description", "Mô tả công việc", "textarea", i.job_description, !editable, ai.has("job_description"))}
    <div id="check-result"></div>
    ${editable ? `<div class="row"><button id="save">Lưu nháp</button><button id="check">Kiểm tra theo quy chế</button><button class="primary" id="submit">Xác nhận & nộp hồ sơ</button></div>` : ""}`;
  if (!editable) return;
  const collect = () => {
    const body = { version: i.version, ai_fields: [...ai] };
    FIELDS.forEach(([n]) => { const v = $(`#f-${n}`).value.trim(); body[n] = v || null; });
    return body;
  };
  FIELDS.forEach(([n]) => $(`#f-${n}`).addEventListener("input", () => { ai.delete(n); $(`[data-field=${n}]`).classList.remove("ai"); }));
  const save = async () => { const r = await api("PATCH", `/internships/${i.id}`, collect()); i.version = r.version; return r; };
  $("#save").onclick = () => run(save, "Đã lưu nháp");
  $("#check").onclick = async () => { await run(save); showChecks((await api("POST", `/internships/${i.id}/validate`)).results); };
  $("#submit").onclick = async () => {
    await run(save);
    try { await api("POST", `/internships/${i.id}/submit`); toast("Đã nộp hồ sơ — chờ giảng viên duyệt"); route(); }
    catch (e) { if (e.detail?.errors) showChecks(e.detail.errors); else toast(e.message); }
  };
  $("#intake").onchange = async (ev) => {
    const file = ev.target.files[0];
    if (!file) return;
    const fd = new FormData(); fd.append("file", file);
    $("#intake-result").innerHTML = `<p class="muted">Đang đọc file…</p>`;
    let r;
    try { r = await api("POST", "/intake/extract", fd, true); } catch (e) { $("#intake-result").innerHTML = `<p class="errors">${esc(e.message)}</p>`; return; }
    const rows = Object.entries(r.fields).map(([k, v]) => `<tr><td>${esc((FIELDS.find((f) => f[0] === k) || [k, k])[1])}</td><td>${v.needs_manual ? '<span class="muted">cần nhập tay</span>' : esc(v.value)}</td><td>${Math.round(v.confidence * 100)}%</td></tr>`).join("");
    $("#intake-result").innerHTML = `<div class="ai-box"><div class="ai-label">${esc(r.label)} · nguồn: ${r.source === "llm" ? "mô hình AI" : "bộ trích xuất theo luật"}${r.matched_company ? ` · khớp DN đã có: ${esc(r.matched_company.name)}` : ""}</div>
      <div class="table-wrap"><table><tr><th>Trường</th><th>Giá trị gợi ý</th><th>Độ tin cậy</th></tr>${rows}</table></div>
      <div class="row" style="margin-top:8px"><button class="primary" id="apply-ai">Điền vào form</button></div></div>`;
    $("#apply-ai").onclick = () => {
      Object.entries(r.fields).forEach(([k, v]) => {
        if (v.needs_manual || !$(`#f-${k}`)) return;
        $(`#f-${k}`).value = v.value; ai.add(k); $(`[data-field=${k}]`).classList.add("ai");
      });
      toast("Đã điền gợi ý — kiểm tra các trường tô tím trước khi nộp");
    };
  };
}

function showChecks(results) {
  const fails = results.filter((r) => r.passed === false || r.passed === undefined);
  $("#check-result").innerHTML = fails.length
    ? `<ul class="errors">${fails.map((r) => `<li>${esc(r.message)} ${cite(r.citation)}</li>`).join("")}</ul>`
    : `<p class="badge ok">Hồ sơ đạt mọi kiểm tra của quy chế</p>`;
}

function renderTimeline(i) {
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

function extensionForm(milestoneId, i) {
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

function renderOutline(i) {
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

async function studentLogs() {
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

// ------------------------------------------------------------------ TRỢ LÝ AI
function assistantView() {
  $("#app").innerHTML = `<div class="card"><h1>Trợ lý chính sách thực tập</h1>
    <p class="muted small">Trợ lý chỉ trả lời theo văn bản quy định đang có hiệu lực và luôn dẫn nguồn. Trợ lý không duyệt hay cam kết kết quả — mọi quyết định do giảng viên đưa ra.</p>
    <div class="chat" id="chat"></div>
    <form class="row" id="ask" style="margin-top:10px"><input id="q" placeholder="Ví dụ: Thời gian thực tập tối thiểu là bao lâu?" maxlength="2000" style="flex:1"><button class="primary">Hỏi</button></form>
    <div class="row small" style="margin-top:8px">${["Thời gian thực tập tối thiểu là bao nhiêu tuần?", "Khi nào phải nộp đề cương?", "Em có được gia hạn nộp báo cáo không?", "Mỗi tuần cần bao nhiêu giờ?"].map((s) => `<button class="link" data-suggest="${esc(s)}">${esc(s)}</button>`).join("")}</div></div>`;
  drawChat();
  document.querySelectorAll("[data-suggest]").forEach((b) => (b.onclick = () => { $("#q").value = b.dataset.suggest; $("#ask").requestSubmit(); }));
  $("#ask").onsubmit = async (ev) => {
    ev.preventDefault();
    const q = $("#q").value.trim();
    if (!q) return;
    $("#q").value = "";
    state.chat.push({ role: "user", content: q });
    const msg = { role: "assistant", content: "", status: "Đang gửi câu hỏi…" };
    state.chat.push(msg);
    drawChat();
    try {
      await streamChat(q, (ev) => {
        if (ev.type === "stage") msg.status = ev.label + "…";
        else if (ev.type === "delta") { msg.status = ""; msg.content += ev.text; }
        else if (ev.type === "done") {
          state.conversationId = ev.conversation_id;
          Object.assign(msg, { content: ev.answer, citations: ev.citations, suggest: ev.suggest_extension, mode: ev.mode, status: "" });
        } else if (ev.type === "error") throw new Error(ev.detail);
        drawChat();
      });
    } catch (e) {
      Object.assign(msg, { content: e.message, status: "" });
    }
    drawChat();
  };
}

/* Đọc SSE từ POST /assistant/chat/stream (EventSource không hỗ trợ POST + header). */
async function streamChat(message, onEvent) {
  const res = await fetch(API + "/assistant/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: "Bearer " + state.token },
    body: JSON.stringify({ message, conversation_id: state.conversationId }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(errorText(data?.detail) || `Lỗi ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let cut;
    while ((cut = buffer.indexOf("\n\n")) >= 0) {
      const frame = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      const line = frame.split("\n").find((l) => l.startsWith("data: "));
      if (line) onEvent(JSON.parse(line.slice(6)));
    }
  }
}

function drawChat() {
  const el = $("#chat");
  if (!el) return;
  el.innerHTML = state.chat.map((m) => `<div class="msg ${m.role}">${m.status ? `<span class="muted small">${esc(m.status)}</span>` : ""}${esc(m.content)}
    ${m.mode?.startsWith("extractive") ? `<div class="small muted" style="margin-top:6px">Trích nguyên văn quy định (không diễn giải).</div>` : ""}
    ${m.citations?.length ? `<div class="cites"><b>Nguồn:</b>${m.citations.map((c) => `<details><summary>[${c.n}] ${esc(c.label)}</summary><div class="pre">${esc(c.excerpt)}</div></details>`).join("")}</div>` : ""}
    ${m.suggest ? `<div style="margin-top:8px"><a href="#/">→ Mở mục Mốc để tạo yêu cầu gia hạn</a></div>` : ""}</div>`).join("") || `<p class="muted">Hãy đặt câu hỏi về thủ tục, thời hạn hay quy định thực tập.</p>`;
  el.scrollTop = el.scrollHeight;
}

// ------------------------------------------------------------------ QUY ĐỊNH
async function policiesView() {
  const docs = await api("GET", "/policies");
  $("#app").innerHTML = `<div class="card"><h1>Văn bản quy định</h1><div class="table-wrap"><table>
    <tr><th>Số hiệu</th><th>Tên văn bản</th><th>Hiệu lực</th><th>Trạng thái</th><th>Số đoạn</th></tr>
    ${docs.map((d) => `<tr><td><button class="link" data-doc="${d.id}">${esc(d.code)}</button></td><td>${esc(d.title)}<div class="small muted">${esc(d.issuer)}</div></td>
      <td>${fmtDate(d.effective_from)}${d.effective_to ? " – " + fmtDate(d.effective_to) : ""}</td><td>${badge(d.status)}</td><td>${d.chunk_count}</td></tr>`).join("")}
    </table></div><div id="doc-view"></div></div>
    ${state.me.can_manage_policies ? `<div class="card"><h2>Tải văn bản mới</h2><form id="pol-form">
      <div class="grid2"><div class="field"><label>Số hiệu</label><input name="code" required></div><div class="field"><label>Tên văn bản</label><input name="title" required></div>
      <div class="field"><label>Hiệu lực từ</label><input type="date" name="effective_from" required></div><div class="field"><label>Thay thế văn bản (số hiệu, nếu có)</label><input name="supersedes_code"></div>
      <div class="field"><label>Cơ quan ban hành</label><input name="issuer"></div><div class="field"><label>File (PDF/DOCX/MD/TXT, có dòng "Điều N.")</label><input type="file" name="file" accept=".pdf,.docx,.md,.txt" required></div></div>
      <button class="primary">Tải lên & lập chỉ mục</button></form></div>` : ""}`;
  document.querySelectorAll("[data-doc]").forEach((b) => (b.onclick = async () => {
    const d = await api("GET", `/policies/${b.dataset.doc}`);
    $("#doc-view").innerHTML = `<h2 style="margin-top:14px">${esc(d.code)} — ${esc(d.title)}</h2>${d.chunks.map((c) => `<details><summary>${esc(c.path)}</summary><p class="pre">${esc(c.text)}</p></details>`).join("")}`;
  }));
  if ($("#pol-form")) $("#pol-form").onsubmit = async (ev) => {
    ev.preventDefault();
    const fd = new FormData(ev.target);
    if (!fd.get("supersedes_code")) fd.delete("supersedes_code");
    await run(() => api("POST", "/policies", fd, true), "Đã tải và lập chỉ mục văn bản");
    route();
  };
}

// ------------------------------------------------------------------ GIẢNG VIÊN
async function lecturerQueue() {
  const q = await api("GET", "/approvals/queue");
  const empty = !q.internships.length && !q.outlines.length && !q.extensions.length;
  $("#app").innerHTML = `<h1>Hàng chờ phê duyệt</h1>${empty ? `<div class="card muted">Không có mục nào chờ duyệt.</div>` : ""}
    ${q.internships.map((i) => `<div class="card"><div class="row spread"><h2>Hồ sơ đăng ký — ${esc(i.student.full_name)}</h2>${badge(i.status)}</div>
      <div class="grid2 small">${FIELDS.map(([n, l]) => `<div><span class="muted">${l}${(i.ai_fields || []).includes(n) ? ' <span class="badge" style="color:var(--ai)">AI điền</span>' : ""}</span><div>${esc(n.endsWith("date") ? fmtDate(i[n]) : n === "mode" ? (i[n] === "part_time" ? "Bán thời gian" : "Toàn thời gian") : i[n])}</div></div>`).join("")}</div>
      ${decisionBox("internship", i.id, i.version)}</div>`).join("")}
    ${q.outlines.map((o) => `<div class="card"><div class="row spread"><h2>Đề cương — ${esc(o.internship.student.full_name)}</h2><span class="small muted">phiên bản ${o.version}</span></div>
      <p class="pre">${esc(o.content)}</p>${aiOutline(o.ai_summary)}${decisionBox("outline", o.id, o.version)}</div>`).join("")}
    ${q.extensions.map((e) => `<div class="card"><h2>Gia hạn — ${esc(e.student.full_name)}: ${esc(e.milestone.name)}</h2>
      <p>${fmtDate(e.previous_due_date)} → <b>${fmtDate(e.requested_due_date)}</b></p><p class="pre">${esc(e.reason)}</p>
      ${e.evidence_id ? `<p class="small">Minh chứng kèm theo: <button class="link" data-file="${e.evidence_id}">mở file</button></p>` : ""}
      ${e.ai_summary ? `<div class="ai-box"><div class="ai-label">${esc(e.ai_summary.label)}</div><p>${esc(e.ai_summary.summary)}</p>
        ${e.ai_summary.related_clauses.map((c) => `<details><summary class="small">${esc(c.label)}</summary><p class="pre small">${esc(c.text)}</p></details>`).join("")}</div>` : ""}
      ${decisionBox("extension", e.id, null)}</div>`).join("")}`;
  document.querySelectorAll("[data-file]").forEach((b) => (b.onclick = () => openFile(b.dataset.file)));
  bindDecisions();
}

function aiOutline(s) {
  if (!s) return `<p class="muted small">Không có gợi ý AI cho đề cương này.</p>`;
  return `<div class="ai-box"><div class="ai-label">${esc(s.label)}</div><p>${esc(s.summary)}</p>
    ${s.uncovered_outcomes.length ? `<p class="small"><b>Chuẩn đầu ra chưa thấy nhắc tới:</b></p><ul class="small">${s.uncovered_outcomes.map((c) => `<li>${esc(c.code)} — ${esc(c.text)}</li>`).join("")}</ul>` : `<p class="small">Đề cương có nhắc tới mọi chuẩn đầu ra học phần.</p>`}</div>`;
}

function decisionBox(kind, id, version) {
  const options = kind === "extension"
    ? [["approved", "Duyệt gia hạn", "primary"], ["rejected", "Từ chối", "danger"]]
    : [["approved", "Duyệt", "primary"], ["revision_requested", "Yêu cầu chỉnh sửa", ""], ["rejected", "Từ chối", "danger"]];
  return `<div class="field" style="margin-top:10px"><label>Lý do / nhận xét ${kind === "extension" ? "(bắt buộc)" : "(bắt buộc khi không duyệt)"}</label><textarea data-reason="${kind}-${id}" style="min-height:60px"></textarea></div>
    <div class="row">${options.map(([d, t, cls]) => `<button class="${cls}" data-decide="${kind}" data-id="${id}" data-version="${version ?? ""}" data-decision="${d}">${t}</button>`).join("")}</div>`;
}

function bindDecisions() {
  const paths = { internship: (id) => `/internships/${id}/decision`, outline: (id) => `/outlines/${id}/decision`, extension: (id) => `/extensions/${id}/decision` };
  document.querySelectorAll("[data-decide]").forEach((b) => (b.onclick = async () => {
    const { decide, id, version, decision } = b.dataset;
    const body = { decision, reason: $(`[data-reason="${decide}-${id}"]`).value };
    if (version) body.version = Number(version);
    await run(() => api("POST", paths[decide](id), body), "Đã ghi nhận quyết định");
    route();
  }));
}

const summaryFilters = { q: "", status: "", program: "", risk: "", lecturer_id: "", sort: "risk", order: "desc", page: 1 };

function summaryQuery(extra = {}) {
  const p = new URLSearchParams();
  Object.entries({ ...summaryFilters, ...extra }).forEach(([k, v]) => { if (v !== "" && v != null) p.set(k, v); });
  return p.toString();
}

async function lecturerStudents() {
  const isAdmin = state.me.role === "admin";
  const [data, users] = await Promise.all([
    api("GET", `/internships-summary?${summaryQuery({ page_size: 25 })}`),
    isAdmin ? api("GET", "/admin/users") : Promise.resolve([]),
  ]);
  const f = summaryFilters;
  const opt = (value, label, current) => `<option value="${esc(value)}" ${String(current) === String(value) ? "selected" : ""}>${esc(label)}</option>`;
  const pages = Math.max(1, Math.ceil(data.total / data.page_size));
  const sortHead = (key, label) => `<th><button class="link" data-sort="${key}">${label}${f.sort === key ? (f.order === "asc" ? " ▲" : " ▼") : ""}</button></th>`;
  $("#app").innerHTML = `<div class="card"><div class="row spread"><h1>${isAdmin ? "Danh sách thực tập toàn khóa" : "Sinh viên phụ trách"}</h1>
      <div class="row"><button data-export="csv">Xuất CSV</button><button data-export="xlsx">Xuất Excel</button></div></div>
    <div class="grid2">
      <div class="field"><label>Tìm (tên, mã SV, doanh nghiệp)</label><input id="sf-q" value="${esc(f.q)}"></div>
      <div class="field"><label>Trạng thái</label><select id="sf-status">${opt("", "Tất cả", f.status)}${Object.keys(STATUS).filter((s) => ["draft", "submitted", "revision_requested", "approved", "rejected", "in_progress", "completed"].includes(s)).map((s) => opt(s, STATUS[s][0], f.status)).join("")}</select></div>
      <div class="field"><label>Ngành</label><select id="sf-program">${opt("", "Tất cả", f.program)}${["Công nghệ thông tin", "Quản trị kinh doanh"].concat(data.facets.programs).filter((v, i, a) => a.indexOf(v) === i).map((p) => opt(p, p, f.program)).join("")}</select></div>
      <div class="field"><label>Mức rủi ro</label><select id="sf-risk">${[["", "Tất cả"], ["any", "Có cảnh báo"], ["none", "Không cảnh báo"], ["critical", "Nghiêm trọng"], ["warning", "Cảnh báo"], ["info", "Thông tin"]].map(([v, l]) => opt(v, l, f.risk)).join("")}</select></div>
      ${isAdmin ? `<div class="field"><label>Giảng viên</label><select id="sf-lecturer">${opt("", "Tất cả", f.lecturer_id)}${users.filter((u) => u.role === "lecturer").map((u) => opt(u.id, u.full_name, f.lecturer_id)).join("")}</select></div>` : ""}
    </div>
    <p class="small muted">${data.total} hồ sơ · trang ${data.page}/${pages}</p>
    <div class="table-wrap"><table>
      <tr>${sortHead("student", "Sinh viên")}${sortHead("company", "Doanh nghiệp")}${sortHead("status", "Trạng thái")}${sortHead("progress", "% mốc")}${sortHead("next_due", "Mốc kế tiếp")}${sortHead("risk", "Cảnh báo")}${isAdmin ? "<th>GV</th>" : ""}</tr>
      ${data.items.map((r) => `<tr><td><a href="#/internship/${r.id}">${esc(r.student_name)}</a><div class="small muted">${esc(r.student_code)} · ${esc(r.program)}</div></td>
        <td>${esc(r.company || "—")}</td><td>${badge(r.status)}</td><td>${r.progress_pct}%</td>
        <td class="small">${r.next_milestone ? `${esc(r.next_milestone)}<div class="muted">${fmtDate(r.next_due)} ${r.next_status === "overdue" ? badge("overdue") : ""}</div>` : "—"}</td>
        <td>${r.open_flags ? `${badge(r.max_severity, SEVERITY)} ×${r.open_flags}` : '<span class="muted">—</span>'}</td>${isAdmin ? `<td class="small">${esc(r.lecturer)}</td>` : ""}</tr>`).join("") || `<tr><td colspan="7" class="muted">Không có hồ sơ phù hợp.</td></tr>`}
    </table></div>
    <div class="row" style="margin-top:8px"><button id="sf-prev" ${data.page <= 1 ? "disabled" : ""}>← Trước</button><button id="sf-next" ${data.page >= pages ? "disabled" : ""}>Sau →</button></div></div>`;
  const apply = (changes) => { Object.assign(summaryFilters, changes); lecturerStudents(); };
  $("#sf-q").onchange = (e) => apply({ q: e.target.value.trim(), page: 1 });
  $("#sf-status").onchange = (e) => apply({ status: e.target.value, page: 1 });
  $("#sf-program").onchange = (e) => apply({ program: e.target.value, page: 1 });
  $("#sf-risk").onchange = (e) => apply({ risk: e.target.value, page: 1 });
  if ($("#sf-lecturer")) $("#sf-lecturer").onchange = (e) => apply({ lecturer_id: e.target.value, page: 1 });
  $("#sf-prev").onclick = () => apply({ page: f.page - 1 });
  $("#sf-next").onclick = () => apply({ page: f.page + 1 });
  document.querySelectorAll("[data-sort]").forEach((b) => (b.onclick = () => {
    const key = b.dataset.sort;
    apply({ sort: key, order: f.sort === key && f.order === "desc" ? "asc" : "desc", page: 1 });
  }));
  document.querySelectorAll("[data-export]").forEach((b) => (b.onclick = () => downloadExport(b.dataset.export)));
}

/* Tải file xuất có kèm Bearer token (link thường không gửi được header). */
async function downloadExport(format) {
  const query = summaryQuery({ format, page: undefined });
  const res = await fetch(`${API}/internships-summary/export?${query}`, { headers: { Authorization: "Bearer " + state.token } });
  if (!res.ok) return toast(`Không xuất được file (${res.status})`);
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = (res.headers.get("content-disposition") || "").split('filename="')[1]?.replace('"', "") || `danh-sach.${format}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function lecturerInternship(id) {
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

async function lecturerFlags() {
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

// ------------------------------------------------------------------ QUẢN TRỊ (tùy chọn)
async function adminHome() {
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

function templateRow(t) {
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

// ------------------------------------------------------------------ router
async function route() {
  if (!state.me) return renderLogin();
  renderShell();
  const parts = (location.hash || "#/").slice(2).split("/");
  const role = state.me.role;
  try {
    if (parts[0] === "assistant") return assistantView();
    if (parts[0] === "policies") return await policiesView();
    if (role === "student") return parts[0] === "logs" ? await studentLogs() : await studentHome();
    if (role === "lecturer") {
      if (parts[0] === "students") return await lecturerStudents();
      if (parts[0] === "internship" && parts[1]) return await lecturerInternship(parts[1]);
      if (parts[0] === "flags") return await lecturerFlags();
      return await lecturerQueue();
    }
    if (parts[0] === "students") return await lecturerStudents();
    if (parts[0] === "internship" && parts[1]) return await lecturerInternship(parts[1]);
    return await adminHome();
  } catch (e) {
    $("#app").innerHTML = `<div class="card errors">${esc(e.message)}</div>`;
  } finally {
    refreshBell();
  }
}

async function boot() {
  // Callback SSO trả token trong fragment: #/sso/<token> hoặc #/sso-error/<lý do>
  if (location.hash.startsWith("#/sso/")) {
    state.token = location.hash.slice("#/sso/".length);
    storage("set", "vin15_token", state.token);
    history.replaceState(null, "", "#/");
  } else if (location.hash.startsWith("#/sso-error/")) {
    const reason = decodeURIComponent(location.hash.slice("#/sso-error/".length));
    history.replaceState(null, "", "#/");
    setTimeout(() => toast("Đăng nhập SSO thất bại: " + reason), 0);
  }
  state.token = state.token || storage("get", "vin15_token");
  if (!state.token) return renderLogin();
  try {
    [state.me, state.config] = await Promise.all([api("GET", "/me"), api("GET", "/config")]);
  } catch (_) {
    return logout();
  }
  route();
}

$("#logout").onclick = logout;
$("#bell").onclick = async () => {
  const p = $("#notif-panel");
  p.hidden = !p.hidden;
  if (!p.hidden) { await api("POST", "/notifications/read-all"); $("#bell-count").hidden = true; }
};
window.addEventListener("hashchange", () => { $("#notif-panel").hidden = true; route(); });
boot();
