import { FIELDS } from "../core/config.js";
import { $, esc, cite, toast } from "../core/utils.js";
import { api, run } from "../core/api.js";
import { route } from "../router.js";

// Form đăng ký thực tập (kèm điền tự động từ file bằng AI).

export function fieldInput(name, label, type, value, disabled, ai) {
  const dis = disabled ? "disabled" : "";
  let input;
  if (type === "textarea") input = `<textarea id="f-${name}" ${dis}>${esc(value)}</textarea>`;
  else if (type === "mode") input = `<select id="f-${name}" ${dis}><option value="full_time" ${value === "full_time" ? "selected" : ""}>Toàn thời gian</option><option value="part_time" ${value === "part_time" ? "selected" : ""}>Bán thời gian</option></select>`;
  else input = `<input id="f-${name}" type="${type === "date" ? "date" : "text"}" value="${esc(value)}" ${dis}>`;
  return `<div class="field ${ai ? "ai" : ""}" data-field="${name}"><label for="f-${name}">${label}${ai ? '<span class="ai-tag">✦ AI điền — hãy kiểm tra</span>' : ""}</label>${input}</div>`;
}

export function renderForm(i, editable) {
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

export function showChecks(results) {
  const fails = results.filter((r) => r.passed === false || r.passed === undefined);
  $("#check-result").innerHTML = fails.length
    ? `<ul class="errors">${fails.map((r) => `<li>${esc(r.message)} ${cite(r.citation)}</li>`).join("")}</ul>`
    : `<p class="badge ok">Hồ sơ đạt mọi kiểm tra của quy chế</p>`;
}
